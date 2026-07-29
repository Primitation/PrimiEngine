# Core Concepts: World, Actors & Components

PacEngine splits "what exists in the scene" into two cooperating pieces:

- **`ActorSubsystem` (`Actors`)** owns *lifetime and ticking* — it decides
  which actors exist and calls `update(dt)` on them every frame.
- **`World`** owns *scene membership/visibility* — the renderer iterates
  `World` to know what to draw, and gameplay code queries it to find actors
  (`World.find(Player)`).

An actor can be registered with `Actors` without being in `World` (this
happens if you construct an actor directly, e.g. `Player(...)`, since
`AActor.__init__` calls `Actors.add(self)` but nothing adds it to `World`).
In practice, always create gameplay actors through **`Actors.spawn(...)`**,
which does both.

## `AActor`

`AActor` is the base class for anything the `ActorSubsystem` manages. It is
intentionally minimal:

```python
class AActor:
    def __init__(self, position=None, scale=None, static=False):
        ...
```

- `position` — a `Vector2`, defaults to `Vector2.zero()`.
- `scale` — a `Vector2`, defaults to `Vector2(1, 1)`.
- `static` — actors flagged `static=True` are eligible to be pre-rendered
  once into the background via `Renderer.bake()` (see
  [04 - Rendering](04-rendering.md)), and are skipped by boundary/blocking
  collision resolution.
- `self.components` — an ordered list of attached `Component` instances.
- `self.logger` — a ready-to-use named logger (`Log.get(self.__class__.__name__)`).
- `self.alive` — set to `False` by `destroy()`; `ActorSubsystem.update()`
  removes dead actors from both `Actors` and `World` at the end of each tick.

### Attaching components

```python
self.sprite = self.add_component(SpriteComponent("player.png"))
self.collider = self.add_component(ColliderComponent(tag="Player"))
```

`add_component` appends the component, calls its `on_added(self)` hook, and
returns it, so you can assign and attach in one line. Components tick **in
the order they were added**, before the actor's own `update(dt)` runs — so
if one component's behavior depends on another (e.g. a particle trail that
reads the current facing direction), attach the dependency first.

```python
component = actor.get_component(ColliderComponent)     # first match, or None
components = actor.get_components(SomeType)             # every match
actor.remove_component(component)                        # detaches + destroys it
```

### Rotation & pivot

`AActor` exposes `rotation` (degrees, 0 = facing +x/right, increasing
clockwise on screen) and `pivot` (fraction of sprite size, default
`(0.5, 0.5)` = center) as properties backed by `_rotation`/`_pivot`. The
renderer reads both when drawing a sprite.

### The update loop

```python
def _tick(self, dt):
    for component in list(self.components):
        if component.enabled and component.alive:
            component.update(dt)
    self.update(dt)

def update(self, dt):
    pass  # override this in your subclass
```

Override `update(dt)` in your actor subclasses for actor-level behavior
(movement, state machines, etc). `dt` is in **milliseconds** throughout the
engine (`Actors.update(dt)`, `Collision`, `Particles.update(dt)` all share
this convention).

### `destroy()`

```python
def destroy(self):
    for component in list(self.components):
        component.destroy()
    self.components.clear()
    self.alive = False
```

Calling `actor.destroy()` tears down every attached component (which lets
e.g. `ColliderComponent.destroy()` unregister itself from `Collision`) and
marks the actor dead. It does **not** immediately remove the actor from
`Actors`/`World` — that happens on the next `Actors.update(dt)` call, which
sweeps up anything with `alive == False`.

## `Component`

```python
class Component(ABC):
    def __init__(self, enabled: bool = True):
        self.actor = None
        self.enabled = enabled
        self.alive = True
        self.local_position = (0.0, 0.0)
        self.offset_rotates = True
```

Subclass this for anything an actor can carry: sprites, colliders,
movement, particle trails, health, etc. The three hooks you'll typically
override:

- **`on_added(self, actor)`** — called once, right after the component is
  appended to `actor.components`. `self.actor` is set for you by
  `super().on_added(actor)`. Do setup here that needs `self.actor` to
  already exist (e.g. `Collision.register(owner=actor, ...)`).
- **`update(self, dt)`** — per-frame work. Only called while
  `enabled and alive` and the owning actor is alive.
- **`destroy(self)`** — release anything external (unregister from
  `Collision`, cancel a pending load, etc). **Always call
  `super().destroy()`** so `alive` becomes `False`.

### `get_world_position()`

Every `Component` can carry a `local_position` offset from its actor
(a plain `(x, y)` tuple or anything with `.x`/`.y`, e.g. a `Vector2`).
`get_world_position()` returns the actor's position plus that offset,
**rotated around the actor's origin by the actor's current rotation** when
`offset_rotates=True` (the default):

```python
self.add_component(ParticleTrailComponent(
    local_offset=(-16, 0),   # "16 units behind" while facing right
    offset_rotates=True,     # rotates to stay "behind" as the actor turns
))
```

This is what lets things like exhaust trails or turret mount points stay in
the right place relative to a rotating actor.

## `World`

```python
World.add(actor)
World.remove(actor)
World.clear()
World.find(Player)          # first actor that is an instance of Player
World.find_all(Ghost)        # every actor that is an instance of Ghost
for actor in World:          # World is iterable
    ...
len(World)
```

`World` is a thin ordered list with class-based lookup helpers. The
renderer (`Renderer.render_draw(world)` / `Renderer.bake(world)`) takes
`World` as an explicit parameter rather than importing the global directly,
so in principle you could maintain multiple `World`-like containers (e.g.
separate front/back layers) — though the shipped engine uses the single
global `World` everywhere.

## `Actors` (the `ActorSubsystem`)

```python
Actors.spawn(ActorClass, *args, **kwargs)   # construct, register, add to World
Actors.update(dt)                            # tick everyone, sweep the dead
Actors.pause() / Actors.resume() / Actors.toggle_pause()
Actors.clear()
Actors.tick                                   # an Event you can also subscribe to
```

- `spawn()` supports a `random_spawn=True` kwarg: if the actor class exposes
  a `get_rect()` method, the subsystem rejection-samples a screen position
  that doesn't overlap any other actor with a `get_rect()`, and sets
  `actor.position` to it before adding it to `World`.
- While `Actors.paused` is `True`, `update(dt)` skips ticking (no
  `tick.emit(dt)`), but **still sweeps dead actors** every call, so cleanup
  doesn't pile up waiting for a resume.
- `Actors.tick` is a plain `Event` (simple pub/sub — see
  `Engine.ActorSubsystem.actorsubsystem.Event`). Any system, not just
  actors, can `Actors.tick.subscribe(callback)` to run logic once per
  actor-tick.

## `on_end_of_anim`

A decorator for chaining a callback onto the *next* `set_animation()` call a
method makes on an `AnimatedSpriteComponent`, without disturbing any
`on_complete` that call already passes:

```python
from Engine import on_end_of_anim, AnimatedSpriteComponent

class Player(Actor):
    @on_end_of_anim(lambda self: self.destroy())
    def dead(self, animation: AnimatedSpriteComponent):
        animation.set_animation(
            "assets/texture/spritesheets/pacman_hd/PacManAssets-PacMan.png",
            frame_width=32, frame_height=32,
            frame_count=8, fps=4, loop=False, start_frame=4,
        )
```

Calling `self.dead(self.animation)` plays the death animation, and once it
finishes (`loop=False` clip reaching its last frame), `self.destroy()` is
called automatically — without `dead()` itself needing to know or pass
`on_complete=`.
