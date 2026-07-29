import math
import random

from .. import Vector2, Log, log_timing
from .. import Assets, SpriteSheetKey, Animation


class Particle:
    """Plain data — no Component/Actor machinery. A burst can be
    dozens of these at once and they only live a fraction of a
    second, so keeping them cheap matters more than giving them the
    full actor lifecycle.

    Draws as a flat-colored square by default. Optionally carries a
    static sprite (sprite_path) or a sprite-sheet animation
    (_animation_key) instead — see ParticleSubsystem.emit()'s
    sprite=/animation= params. `sprite` (the property below) is what
    ParticleSubsystem.render() actually checks each frame; it's None
    for flat-color particles."""

    __slots__ = (
        "position", "velocity", "color", "size",
        "life", "max_life", "gravity", "fade",
        "rotation", "angular_velocity", "face_velocity",
        "sprite_path", "scale",
        "_animation_key", "_animation", "_animation_time",
        "_fps", "_loop",
    )

    def __init__(
        self, position, velocity, color, size, life, gravity, fade,
        rotation=0.0, angular_velocity=0.0, face_velocity=False,
        sprite_path=None, scale=1.0,
        animation_key=None, fps=10.0, loop=True,
    ):
        self.position = position
        self.velocity = velocity
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life
        self.gravity = gravity
        self.fade = fade

        self.rotation = rotation
        self.angular_velocity = angular_velocity
        self.face_velocity = face_velocity

        self.sprite_path = sprite_path
        self.scale = scale

        self._animation_key = animation_key
        self._animation = None
        self._animation_time = 0.0
        self._fps = fps
        self._loop = loop

    @property
    def t(self):
        """0.0 at spawn, 1.0 the instant it dies — drives the fade
        curve in ParticleSubsystem.render()."""
        if self.max_life <= 0:
            return 1.0
        return 1.0 - max(0.0, self.life) / self.max_life

    @property
    def sprite(self):
        """This particle's current sprite, or None to fall back to a
        flat-colored square. A static sprite_path takes priority;
        otherwise resolves the shared Animation for _animation_key —
        same caching model as AnimatedSpriteComponent, frames sliced
        once per unique key and shared across every particle (and
        every actor) using that sheet."""

        if self.sprite_path is not None:
            return Assets.get(self.sprite_path)

        if self._animation_key is not None:
            if self._animation is None:
                frames = Assets.get(self._animation_key)
                if frames is None:
                    return None
                self._animation = Animation(frames, fps=self._fps, loop=self._loop)
            return self._animation.frame_at(self._animation_time)

        return None


class ParticleSubsystem:
    """One-shot particle bursts for visual feedback — impacts,
    deaths, pickups, whatever needs a bit of juice. Not tied to
    Actors/Components at all: emit() fires a burst of plain
    position/velocity/color/lifetime particles that this subsystem
    itself ticks and draws.

    By default particles draw as flat-colored squares
    (Renderer.draw_rect) — cheap, no asset needed. Pass sprite= or
    animation= to emit() to draw real (optionally animated) sprites
    instead, using the normal alpha-blended Renderer.draw_sprite
    path and AssetSubsystem's usual caching.

    Call update(dt) once per frame (same dt-in-ms convention as
    ActorSubsystem/CollisionSubsystem) and render(Renderer) once per
    frame — after render_draw(world) and before render_present(), so
    particles land in the same frame instead of one that's already
    been presented (see RendererSubsystem.render_draw/render_present).
    """

    def __init__(self, max_particles: int = 2000):
        self._particles = []
        self.max_particles = max_particles
        self._logger = Log.get("particles")

    def emit(
        self,
        position,
        count: int = 12,
        color=0xFFFFFFFF,
        speed=(50.0, 150.0),
        size=(2.0, 4.0),
        life=(0.25, 0.5),
        direction: float = 0.0,
        spread: float = 360.0,
        gravity: float = 0.0,
        fade: bool = True,
        sprite=None,
        animation: dict = None,
        scale=(1.0, 1.0),
        rotation=(0.0, 0.0),
        angular_velocity=(0.0, 0.0),
        face_velocity: bool = False,
    ):
        """Spawn a one-shot burst of `count` particles at `position`
        (a Vector2 — copied per-particle, not shared/mutated).

        speed / size / life: (min, max) ranges. Each particle rolls
        its own value uniformly inside that range so a burst doesn't
        look perfectly uniform. `size` only matters for flat-color
        particles (see sprite/animation below) — sprite particles use
        their sprite's own native size instead.

        direction: center angle in degrees the burst is aimed along
        (0 = +x/right, 90 = +y/down — same convention as
        AActor.rotation). spread: total cone width in degrees around
        direction — 360 (default) scatters evenly in every direction;
        a small spread gives a directional spray, e.g. sparks off a
        wall bounce.

        color: a single 0xAARRGGBB int, or a list/tuple of them to
        pick from randomly per particle. Ignored (except as the fade
        source, see below) for sprite/animation particles — the
        sprite's own pixels draw as-is, there's no tint/multiply.

        gravity: units/sec^2 added to vertical velocity every frame —
        0 for particles that just drift on their initial velocity,
        positive to have them arc/fall.

        fade: if True, alpha ramps from the color's own alpha down to
        0 over the particle's lifetime. For flat-color particles this
        blends smoothly; for sprite/animation particles there's no
        partial-alpha draw_sprite path, so a faded sprite particle
        just disappears (skips drawing) once its rolled alpha would
        be ~0 rather than really fading out pixel-by-pixel.

        sprite: a static image path (or list of paths to pick from
        randomly per particle) to draw each particle as, instead of a
        flat-colored square. Takes priority over `animation` if both
        are given.

        animation: dict describing a sprite-sheet clip to play per
        particle — {"path", "frame_width", "frame_height",
        "frame_count", "columns", "start_frame", "fps", "loop"}.
        Frames are sliced once per unique combo and shared across
        every particle (and actor) using it, same caching model as
        AnimatedSpriteComponent. Each particle plays independently
        from frame 0.

        scale: (min, max) uniform scale factor applied to the
        sprite's/animation's native size. Ignored for flat-color
        particles (which use `size` instead).

        rotation: (min, max) degrees — fixed starting rotation,
        rolled once per particle. Ignored if face_velocity=True.

        angular_velocity: (min, max) degrees/sec — constant spin,
        applied every frame on top of rotation (still applies even
        with face_velocity=True, e.g. a spark that both flies forward
        and tumbles).

        face_velocity: if True, rotation instead continuously tracks
        the particle's current velocity direction — good for
        streaks/sparks that should visually point where they're
        flying, rather than holding a fixed rotation.
        """

        if len(self._particles) >= self.max_particles:
            return

        colors = color if isinstance(color, (list, tuple)) else (color,)
        count = min(count, self.max_particles - len(self._particles))

        sprite_paths = None
        if sprite is not None:
            sprite_paths = sprite if isinstance(sprite, (list, tuple)) else (sprite,)
            for path in sprite_paths:
                Assets.queue(path)

        animation_key = None
        anim_fps, anim_loop = 10.0, True

        if sprite_paths is None and animation is not None:
            animation_key = SpriteSheetKey(
                animation["path"],
                animation["frame_width"],
                animation["frame_height"],
                animation.get("frame_count"),
                animation.get("columns"),
                animation.get("start_frame", 0),
            )
            anim_fps = animation.get("fps", 10.0)
            anim_loop = animation.get("loop", True)
            Assets.queue(animation_key)

        for _ in range(count):
            spawn_angle = direction + random.uniform(-spread / 2, spread / 2)
            angle = math.radians(spawn_angle)
            spd = random.uniform(*speed)

            velocity = Vector2(math.cos(angle) * spd, math.sin(angle) * spd)

            start_rotation = spawn_angle if face_velocity else random.uniform(*rotation)

            self._particles.append(
                Particle(
                    position=Vector2(position.x, position.y),
                    velocity=velocity,
                    color=random.choice(colors),
                    size=random.uniform(*size),
                    life=random.uniform(*life),
                    gravity=gravity,
                    fade=fade,
                    rotation=start_rotation,
                    angular_velocity=random.uniform(*angular_velocity),
                    face_velocity=face_velocity,
                    sprite_path=random.choice(sprite_paths) if sprite_paths else None,
                    scale=random.uniform(*scale),
                    animation_key=animation_key,
                    fps=anim_fps,
                    loop=anim_loop,
                )
            )

    def clear(self):
        """Kill every live particle immediately (e.g. on level
        reset)."""
        self._particles.clear()

    @log_timing()
    def update(self, dt):
        """Call once per frame, dt in ms — same convention as
        ActorSubsystem.update(dt)."""

        seconds = dt / 1000.0
        alive = []

        for particle in self._particles:
            particle.life -= seconds

            if particle.life <= 0:
                continue

            particle.velocity.y += particle.gravity * seconds
            particle.position += particle.velocity * seconds

            if particle._animation_key is not None:
                particle._animation_time += dt

            if particle.face_velocity:
                particle.rotation = math.degrees(
                    math.atan2(particle.velocity.y, particle.velocity.x)
                )

            particle.rotation += particle.angular_velocity * seconds

            alive.append(particle)

        self._particles = alive

    def render(self, renderer):
        """Call once per frame — draws every live particle, fading
        alpha out over its lifetime when fade=True. Call this after
        renderer.render_draw(world) and before renderer.render_present()
        so particles land in the same presented frame."""

        for particle in self._particles:
            sprite = particle.sprite

            if sprite is not None:
                if particle.fade:
                    base_alpha = (
                        (particle.color >> 24) & 0xFF
                        if isinstance(particle.color, int) else 255
                    )
                    if base_alpha * (1.0 - particle.t) < 1:
                        # Faded below ~invisible — skip the draw
                        # entirely (draw_sprite has no partial-alpha
                        # tint of its own to fade smoothly with).
                        continue

                width = sprite.width * particle.scale
                height = sprite.height * particle.scale

                top_left = Vector2(
                    particle.position.x - width / 2,
                    particle.position.y - height / 2,
                )

                renderer.draw_sprite(
                    sprite,
                    top_left,
                    particle.scale,
                    particle.rotation,
                    (0.5, 0.5),
                )
                continue

            color = particle.color

            if particle.fade:
                base_alpha = (color >> 24) & 0xFF
                alpha = int(base_alpha * (1.0 - particle.t))
                color = (alpha << 24) | (color & 0x00FFFFFF)

            half = particle.size / 2
            renderer.draw_rect(
                particle.position.x - half,
                particle.position.y - half,
                particle.size,
                particle.size,
                color,
            )

    @property
    def count(self):
        return len(self._particles)


# Global particle system
Particles = ParticleSubsystem()
