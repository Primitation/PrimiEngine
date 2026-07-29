# Particles

`Particles` (an instance of `ParticleSubsystem`) drives one-shot particle
bursts for visual feedback — impacts, deaths, pickups, trails. Particles
are **plain data**, not `Actor`/`Component`s — a burst can be dozens of
these at once and they only live a fraction of a second, so keeping them
cheap matters more than giving them the full actor lifecycle.

## Per-frame update

```python
Particles.update(dt)          # dt in ms — same convention as Actors.update
Particles.render(Renderer)     # call AFTER Renderer.render_draw(), BEFORE Renderer.render_present()
```

`update` is wrapped with `@log_timing()` (logs average timing at DEBUG
level every 300 calls). `render` must run in between the draw and present
steps so particles land in the *same* frame that gets shown, not one
that's already been presented:

```python
Renderer.render_draw(World)
Particles.update(dt)
Particles.render(Renderer)
Renderer.render_present()
```

## Emitting a burst

```python
from Engine import Particles, Vector2

Particles.emit(
    Vector2(player.position.x, player.position.y),
    count=12,
    color=0xFFFFFFFF,
    speed=(50.0, 150.0),
    size=(2.0, 4.0),
    life=(0.25, 0.5),
    direction=0.0,
    spread=360.0,
    gravity=0.0,
    fade=True,
)
```

By default particles draw as flat-colored squares
(`Renderer.draw_rect`) — cheap, no asset needed. Every ranged parameter
(`speed`, `size`, `life`, `scale`, `rotation`, `angular_velocity`) is a
`(min, max)` tuple; each particle in the burst rolls its own value
uniformly inside that range so a burst doesn't look perfectly uniform.

Key parameters:

- **`position`** — a `Vector2`, copied per-particle (not shared/mutated).
- **`direction`** — center angle in degrees the burst is aimed along
  (`0` = +x/right, `90` = +y/down — same convention as `AActor.rotation`).
- **`spread`** — total cone width in degrees around `direction`. `360`
  (default) scatters evenly in every direction; a small spread gives a
  directional spray (e.g. sparks off a wall bounce).
- **`color`** — a single `0xAARRGGBB` int, or a list/tuple to pick from
  randomly per particle. Ignored for sprite/animation particles except as
  the fade-alpha source (see below).
- **`gravity`** — units/sec² added to vertical velocity every frame; `0`
  for particles that just drift on initial velocity, positive to arc/fall.
- **`fade`** — if `True`, alpha ramps from the color's own alpha down to 0
  over the particle's lifetime.

### Sprite / animated particles

```python
Particles.emit(
    position,
    count=8,
    sprite="assets/texture/spark.png",             # or a list to pick from randomly
    scale=(0.5, 1.0),
)

Particles.emit(
    position,
    count=8,
    animation={
        "path": "assets/texture/spritesheets/explosion.png",
        "frame_width": 32, "frame_height": 32,
        "frame_count": 8, "fps": 20.0, "loop": False,
    },
)
```

- `sprite` takes priority over `animation` if both are given.
- Frames for `animation` are sliced once per unique combo and shared
  across every particle (and every actor) using it — same caching model as
  `AnimatedSpriteComponent` (see [05 - Assets](05-assets.md)). Each particle
  plays independently from frame 0.
- `scale` (a `(min, max)` uniform scale factor) applies to the
  sprite's/animation's native size; it's ignored for flat-color particles,
  which use `size` instead.
- For sprite/animation particles there's no partial-alpha draw path, so a
  faded sprite particle just disappears (skips drawing) once its rolled
  alpha would be near-zero, rather than fading pixel-by-pixel.

### Rotation

```python
Particles.emit(
    position,
    rotation=(0.0, 360.0),          # fixed starting rotation, rolled once per particle
    angular_velocity=(-90.0, 90.0),  # constant spin, applied every frame
    face_velocity=True,               # rotation instead continuously tracks velocity direction
)
```

- `rotation` is ignored if `face_velocity=True`.
- `angular_velocity` still applies even with `face_velocity=True` — e.g. a
  spark that both flies forward *and* tumbles.
- `face_velocity=True` is good for streaks/sparks that should visually
  point where they're flying.

## Other operations

```python
Particles.clear()      # kill every live particle immediately (e.g. level reset)
Particles.count          # number of currently-live particles
```

`ParticleSubsystem(max_particles=2000)` caps the total live particle count;
`emit()` silently does nothing (or emits fewer than `count`) once the cap
is hit, rather than growing unbounded.

## Building a component around it: `ParticleTrailComponent`

The shipped example (`assets/code/components/particle_component.py`) shows
the idiomatic way to turn "an actor that moves" into a continuous particle
trail, generically:

```python
self.add_component(ParticleTrailComponent(
    local_offset=(-16, 0),     # offset to the left of the actor center
    offset_rotates=True,        # rotate with the actor
    interval=0.02,               # seconds between emissions while moving
    count=3,
    color=0xFFFF8800,            # orange
    speed=(20, 50),
    size=(3, 6),
    life=(0.2, 1.0),
    spread=45.0,
    min_speed=10.0,               # actor must be moving faster than this to emit
    emit_direction="backward",    # "backward" | "forward" | "random" | a numeric offset
))
```

This component is generic — it only reads `actor.velocity` and
`actor.rotation` each frame, so it works on anything with those two
attributes (e.g. anything carrying a `MovementComponent` /
`FaceDirectionComponent`), without knowing about `Player` specifically.
Note it must be attached **after** whatever sets `rotation` for the frame
(e.g. `FaceDirectionComponent`) — components tick in the order they were
added, so this one needs to run later to see *this* frame's rotation
instead of last frame's.

## Debug aid: `OriginMarkerComponent`

Also shown in the example code — draws a single non-fading, zero-velocity
particle at `actor.position` every frame, piggybacking on `Particles`
instead of adding a new render hook. Handy for confirming whether a sprite
is actually centered on an actor's origin or drawn as a top-left corner
from it. It's explicitly a debugging tool — remove it once you're done
checking, not something to ship.
