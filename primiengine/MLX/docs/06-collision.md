# Collision

`Collision` (an instance of `CollisionSubsystem`) tracks a flat list of
`Collider`s, broad-phases them through a uniform spatial hash, narrow-phases
overlapping pairs, optionally resolves "blocking" pairs physically (push
apart + bounce), and fires begin/end overlap events. It also clamps
non-static colliders to the screen bounds, if `init()` was called.

The easiest way to use collision from an actor is **`ColliderComponent`**
(see below) rather than calling `Collision.register()` directly — but the
lower-level API is documented here too, since `ColliderComponent` is just a
thin wrapper over it.

## Setup

```python
Collision.init(width, height)
```

Call this once at startup (typically right alongside `Renderer.init()`).
Without it, boundary resolution is skipped entirely — colliders simply
won't be clamped to any edge — rather than crashing or clamping everything
to a 0x0 world. A warning is logged (once) if `update()` runs before
`init()`.

## `ColliderComponent`

```python
from Engine import ColliderComponent

self.collider = self.add_component(
    ColliderComponent(
        get_rect=None,          # None = auto (see below)
        tag="Player",
        collides_with=None,      # None = collides with every tag
        blocking=False,
        bounce=0.0,
        static=False,
        enabled=True,
    )
)

self.collider.on_begin_overlap.bind(self._on_hit)
self.collider.on_end_overlap.bind(self._on_unhit)
```

- **`get_rect`** — optional callable returning `(x, y, width, height)`. If
  omitted, the component looks for another component on the same actor that
  exposes `get_rect()` (`SpriteComponent`/`AnimatedSpriteComponent` both
  do) and uses that; failing that, it falls back to a 1x1 box at the
  actor's position scaled by `actor.scale`. Pass your own `get_rect` when
  the hitbox shouldn't just track the visible sprite 1:1 — e.g. a hitbox
  that should ignore a squash/stretch animation on the sprite's scale (see
  `Actor.get_rect` in the shipped example, which pins the hitbox to
  `base_scale` instead of the animated `self.scale`).
- **`tag`** — identifies this collider's type/category.
- **`collides_with`** — `None` (collide with anything) or a list of tags
  this collider is allowed to overlap with. Checked both ways — `a` and
  `b` must each accept the other's tag for the pair to be considered.
- **`blocking`** — if `True` on **both** sides of a pair, an overlap gets
  physically resolved (pushed apart + bounced) each frame instead of just
  firing overlap events. Requires the owner to have a `.position`
  (`Vector2`), and a `.velocity` for bounce to do anything.
- **`bounce`** — restitution, `0..1`. `0` absorbs velocity into the surface
  (stops dead on that axis); `1` is a fully elastic bounce.
- **`static`** — this collider never moves when resolving a block (walls,
  floors) and is never clamped to the world boundary either.

The component registers itself with `Collision` in `on_added()` (once
`self.actor` exists) and unregisters in `destroy()` — so removing/destroying
an actor or component cleans up its collider automatically; you never call
`Collision.unregister()` yourself.

```python
collider.collider              # underlying Collider, for direct access
collider.rect()                 # current (x, y, width, height)
collider.enabled = False         # also disables the underlying Collider
```

## Per-frame update

```python
Collision.update()   # call once per frame
```

Wrapped with `@log_timing()` — every ~300 calls (the decorator's default
`every=300`) it logs the average time this took, at DEBUG level.

## Overlap events

```python
collider.on_begin_overlap.bind(callback)   # callback(self_collider, other_collider)
collider.on_end_overlap.bind(callback)
collider.on_begin_overlap.unbind(callback)
```

Both are `Signal` instances — a minimal multicast delegate (same idea as
Unreal's dynamic multicast delegates). `broadcast()` calls every bound
listener; if one raises, it's logged (`Log.get("collision")`) and skipped
without stopping the rest.

Begin/end are computed by diffing this frame's overlap set against last
frame's — each pair fires **both directions** (`a.on_begin_overlap` with
`(a, b)`, and `b.on_begin_overlap` with `(b, a)`).

## Blocking resolution (push-apart + bounce)

When two `blocking=True` colliders overlap, `CollisionManager._resolve_block`:

1. Computes overlap on both axes and pushes apart along whichever axis has
   the **least** overlap (the "shallow axis" — the direction requiring the
   least movement to separate).
2. Splits the correction 50/50 if both sides are movable (non-static, with
   a `.position`), or gives 100% to whichever side is actually movable if
   only one is.
3. Caps how much penetration gets resolved in a single frame
   (`max_correction_per_frame`, default `64.0`) so a large initial overlap
   (e.g. actors spawned stacked) bleeds off over a few frames instead of
   snapping apart violently in one jump.
4. Only nudges a collider if it's actually moving *into* the surface
   (`velocity.dot(normal) < 0`) — one already moving away is left alone.
5. Bounces velocity off the resolved normal, scaled by that collider's own
   `bounce` restitution.
6. If both centers are exactly coincident (e.g. two actors spawned at the
   identical position), the separation direction is picked deterministically
   from `id(a) ^ id(b)` rather than always defaulting to the same axis.

## Boundary resolution

Every frame (before and after object-object resolution), non-static,
enabled colliders with a `.position` are clamped inside `[0, width] x [0,
height]` (from `Collision.init()`), with velocity zeroed/reflected on
whichever axis the clamp applied to (mirroring off a wall rather than
sticking).

## Broad phase: `SpatialGrid`

Colliders are bucketed into a uniform grid (`cell_size`, default `128`) by
every cell their rect touches; only colliders sharing a cell are checked
against each other in the narrow phase. This turns the naive O(n²) all-pairs
check into roughly O(n) for scenes where actors aren't all crammed
together. Tune `cell_size` (passed through `CollisionSubsystem(cell_size=...)`)
to be in the same ballpark as your typical actor size — too small and
actors span many cells (more insert work); too large and cells degrade
back toward "the whole world is one bucket" (more candidate pairs to
check).

## Direct/low-level API

If you're not going through `ColliderComponent` for some reason:

```python
collider = Collision.register(
    owner, get_rect, tag="default", collides_with=None,
    blocking=False, bounce=0.0, static=False, enabled=True,
)
Collision.unregister(collider)
```
