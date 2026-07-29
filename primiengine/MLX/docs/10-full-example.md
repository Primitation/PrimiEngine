# Full Example Walkthrough

This walks through the shipped example game code under `assets/code/`, a
small Pac-Man-style setup, tying together everything from the other pages.
The class hierarchy is:

```
AActor
 └── Actor              (assets/code/actors/actor.py)
      ├── Entity          (assets/code/actors/entity.py)
      └── Player           (assets/code/actors/player.py)
```

## `Actor` — the project's own base class

```python
from Engine import AActor, Vector2
from Engine import ColliderComponent, SpriteComponent, AnimatedSpriteComponent

class Actor(AActor):
    def __init__(self, position, velocity, scale, tag="Actor"):
        super().__init__(position=position, scale=scale)
        self.velocity = velocity

        # "resting" scale to animate around, kept separate from self.scale
        # (which the renderer reads), so a punch animation can push
        # self.scale up and back down without losing the original size.
        self.base_scale = Vector2(scale.x, scale.y)

        self._collider = self.add_component(
            ColliderComponent(
                get_rect=self.get_rect,
                tag="Actor",
                collides_with=None,
                blocking=False,
                bounce=0.8,
                static=False,
                enabled=True,
            )
        )
        self._collider.on_begin_overlap.bind(self._on_collision_begin)
        self._collider.on_end_overlap.bind(self._on_collision_end)
```

This is a good template for a project-level base actor: it adds a
`velocity` field (the engine's `AActor` doesn't have one by default — see
[02 - Core Concepts](02-core-concepts.md)), and a `ColliderComponent` with a
custom `get_rect` override.

### Why `get_rect` is overridden here

```python
def get_rect(self):
    """Uses base_scale rather than the animated self.scale."""
    sprite_component = (
        self.get_component(SpriteComponent)
        or self.get_component(AnimatedSpriteComponent)
    )
    if sprite_component is not None and sprite_component.sprite is not None:
        width = sprite_component.width * self.base_scale.x
        height = sprite_component.height * self.base_scale.y
    else:
        width, height = self.base_scale.x, self.base_scale.y

    return (self.position.x, self.position.y, width, height)
```

`ColliderComponent`'s default `get_rect` fallback would use the sprite's
size scaled by `actor.scale` — but `actor.scale` is exactly what a
squash/punch animation temporarily distorts. By keying off `base_scale`
instead, the hitbox stays a stable size regardless of any transient visual
scale animation happening on top of it.

### Movement

```python
def update(self, dt):
    if not self.static:
        self.position += self.velocity * (dt / 1000)
```

Straightforward Euler integration — `dt` arrives in milliseconds (the
engine-wide convention), so `dt / 1000` converts to seconds before scaling
velocity.

### Swapping colliders at runtime

```python
def set_collider(self, collider: ColliderComponent):
    self.remove_component(self._collider)
    self._collider = self.add_component(collider)
    self._collider.on_begin_overlap.bind(self._on_collision_begin)
    self._collider.on_end_overlap.bind(self._on_collision_end)
```

Handy if an actor needs a different hitbox shape/tag partway through its
life (e.g. switching from a standing hitbox to a crouching one) — detaches
the old `ColliderComponent` (which unregisters it from `Collision` via its
`destroy()`), attaches the new one, and re-binds the same overlap handlers.

## `Entity`

```python
class Entity(Actor):
    def __init__(self, position, velocity, scale, tag="Actor"):
        super().__init__(position=position, scale=scale, velocity=velocity, tag=tag)
        self._collider = self.add_component(
            ColliderComponent(
                get_rect=self.get_rect, tag="Actor", collides_with=None,
                blocking=False, bounce=0.8, static=False, enabled=True,
            )
        )
        self._collider.on_begin_overlap.bind(self._on_collision_begin)
        self._collider.on_end_overlap.bind(self._on_collision_end)
```

In the shipped code, `Entity` re-does the exact same collider setup
`Actor.__init__` already performed — meaning an `Entity` ends up with two
separate `ColliderComponent`s registered with `Collision` (the first one
from `Actor.__init__`, orphaned but still registered, plus this new one).
If you use `Entity` as a starting point for your own classes, either drop
this duplicate block (relying on the one `Actor.__init__` already sets up),
or explicitly remove the old collider first with
`self.remove_component(self._collider)` before adding the new one, mirroring
`set_collider()` above.

## `Player`

```python
from .actor import Actor
from Engine import on_end_of_anim, Vector2, Input, AnimatedSpriteComponent
from ..components.movement_components import (
    MovementComponent, PlayerMovementInput, FaceDirectionComponent)
from ..components.particle_component import ParticleTrailComponent

class Player(Actor):
    def __init__(self, position, velocity, scale, tag="Actor", speed=200.0):
        super().__init__(position=position, scale=scale, velocity=velocity, tag=tag)

        self.animation = self.add_component(
            AnimatedSpriteComponent(
                "assets/texture/spritesheets/pacman_hd/PacManAssets-PacMan.png",
                frame_width=32, frame_height=32,
                frame_count=4, fps=4, loop=True, start_frame=0,
                center=True,   # box centered on actor.position, unrotated
            )
        )

        self.movement = self.add_component(MovementComponent(speed=speed))
        self.add_component(PlayerMovementInput())
        self.add_component(FaceDirectionComponent())

        self.add_component(ParticleTrailComponent(
            local_offset=(-16, 0), offset_rotates=True,
            interval=0.02, count=3, color=0xFFFF8800,
            speed=(20, 50), size=(3, 6), life=(0.2, 10),
            spread=45.0, min_speed=10.0, emit_direction="backward",
        ))

        Input.bind_action("dead", [Input.KEYS["t"]])
```

This lines up four components in a deliberate order:

1. **`AnimatedSpriteComponent`** — the visible sprite, `center=True` so the
   32x32 frame's box is centered on `actor.position` rather than drawn from
   a top-left corner.
2. **`MovementComponent`** — generic, direction-agnostic movement (see
   [02 - Core Concepts](02-core-concepts.md) / `Component` docs); it doesn't
   care *where* direction comes from.
3. **`PlayerMovementInput`** — reads `Input`'s `"left"/"right"/"up"/"down"`
   actions each frame and calls `movement.set_direction(...)`.
4. **`FaceDirectionComponent`** — sets `actor.rotation` from
   `actor.velocity` (0/90/180/270, facing right/down/left/up).
5. **`ParticleTrailComponent`** — attached *last*, deliberately, so it reads
   this frame's already-updated `rotation` (set by `FaceDirectionComponent`
   just above it) rather than last frame's, when computing where "behind
   the actor" points.

Components tick in the order they were added — this ordering is not
incidental, it's what makes the trail correctly emit behind the actor's
*current* facing direction instead of lagging one frame behind.

### Playing a one-shot death animation with `on_end_of_anim`

```python
@on_end_of_anim(lambda self: self.destroy())
def dead(self, animation: AnimatedSpriteComponent):
    animation.set_animation(
        "assets/texture/spritesheets/pacman_hd/PacManAssets-PacMan.png",
        frame_width=32, frame_height=32,
        frame_count=8, fps=4, loop=False, start_frame=4,
    )

def update(self, dt):
    if Input.is_action_triggered("dead"):
        self.dead(self.animation)
    super().update(dt)
```

Pressing **T** (bound to the `"dead"` action in `__init__`) plays an 8-frame
death clip starting at `start_frame=4` of the same sheet (right after the 4
walk frames), non-looping. `@on_end_of_anim` transparently chains
`self.destroy()` onto the animation's completion — see
[02 - Core Concepts](02-core-concepts.md) for how the decorator works.

## Movement components in detail

```python
class MovementComponent(Component):
    def __init__(self, speed=200.0, enabled=True):
        super().__init__(enabled)
        self.speed = speed
        self.direction = Vector2(0, 0)

    def set_direction(self, direction: Vector2):
        self.direction = direction

    def update(self, dt):
        direction = self.direction
        length = (direction.x**2 + direction.y**2) ** 0.5
        if length > 0:
            direction = Vector2(direction.x/length, direction.y/length)
            self.actor.velocity = Vector2(direction.x*self.speed, direction.y*self.speed)
        else:
            self.actor.velocity = Vector2(0, 0)
```

Normalizes whatever direction it was given, so diagonal movement isn't
faster than axis-aligned movement, then writes `actor.velocity` — which
`Actor.update(dt)` (defined on the base `Actor` class above) then
integrates into `position`.

```python
class PlayerMovementInput(Component):
    def on_added(self, actor):
        super().on_added(actor)
        self.movement = actor.get_component(MovementComponent)

    def update(self, dt):
        direction = Vector2(0, 0)
        if Input.is_action_held("left"):  direction.x -= 1
        if Input.is_action_held("right"): direction.x += 1
        if Input.is_action_held("up"):    direction.y -= 1
        if Input.is_action_held("down"):  direction.y += 1
        self.movement.set_direction(direction)
```

Note: this depends on `MovementComponent` already being attached to the
same actor (it looks it up via `get_component` in `on_added`), so
`MovementComponent` must be added **before** `PlayerMovementInput` — which
is exactly the order `Player.__init__` uses above.

```python
class ChasePlayerComponent(Component):
    def update(self, dt):
        movement = self.actor.get_component(MovementComponent)
        player = World.find("Player")
        direction = Vector2(
            player.position.x - self.actor.position.x,
            player.position.y - self.actor.position.y,
        )
        movement.set_direction(direction)
```

A ready-made "chase the player" AI component — drop it onto any actor that
also has a `MovementComponent`, e.g. a ghost. Note as shipped this passes
the **string** `"Player"` to `World.find`, but `World.find` expects an
actual class (it calls `isinstance(actor, actor_class)`) — pass the
imported `Player` class itself (`World.find(Player)`) instead for this to
work correctly.

```python
class FaceDirectionComponent(Component):
    def update(self, dt):
        velocity = self.actor.velocity
        if velocity.x > 0: self.actor.rotation = 0
        elif velocity.x < 0: self.actor.rotation = 180
        elif velocity.y < 0: self.actor.rotation = 270
        elif velocity.y > 0: self.actor.rotation = 90
```

Simple 4-directional facing from velocity, in the engine's rotation
convention (`0` = +x/right, `90` = +y/down).

## A note on `assets/level/levels.py`

The shipped `levels.py` is a rough sketch rather than working code as-is —
worth knowing if you copy it as a starting point:

```python
class Level(ABC):
    actors: AActor = []

    def load(self):
        World.clear()
        Actors.clear()
        self._spawn_actors()

    def _spawn_actors(self):
        for actor_class, kwargs in self.actors:
            Actors.spawn(actor_class, **kwargs)

    def add_actor(self, actor_class: type, **kwargs):
        self.actors.append((actor_class, kwargs))


class Level_1(Level):
    super.add_actor(Player, Vector2(0, 0), Vector2(0.25, 0.25),
                   "assets.texture.pacman.png")
```

Two things to fix before using this pattern:

1. `actors: AActor = []` is a **class attribute**, shared by every
   subclass and every instance unless overridden — every `Level` subclass
   would append into the *same* list. Give each level its own list in
   `__init__` instead: `self.actors = []`.
2. `Level_1`'s body calls `super.add_actor(...)` at class-definition time
   (not inside a method, and `super` used without `()` or `self`) — this
   doesn't do what's intended. A working version looks like:

```python
class Level_1(Level):
    def __init__(self):
        self.actors = []
        self.add_actor(
            Player,
            position=Vector2(0, 0),
            velocity=Vector2(0, 0),
            scale=Vector2(0.25, 0.25),
        )

# usage:
level = Level_1()
level.load()
```

Also note `Player.__init__` takes `position`, `velocity`, `scale` as
keyword-friendly args (no sprite-path argument — the Pac-Man sprite path is
hardcoded inside `Player.__init__` itself), so pass them as keywords rather
than the three positional args shown in the original snippet.
