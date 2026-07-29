# Math & Types

All of these live under `Engine.Types` and are re-exported from `Engine`
directly: `from Engine import Vector2, Vector3, Quaternion, Euler, Color`.

## `Vector2` / `Vector3`

Plain, `__slots__`-based value types with the arithmetic you'd expect:

```python
a = Vector2(3, 4)
b = Vector2(1, 1)

a + b            # Vector2(4, 5)
a - b            # Vector2(2, 3)
-a               # Vector2(-3, -4)
a * 2            # Vector2(6, 8)      (scalar mul, __rmul__ too: 2 * a works)
a / 2            # Vector2(1.5, 2.0)
a.dot(b)          # 7
a.cross(b)        # scalar (2D "cross" = z-component if treated as 3D)
a.length()        # 5.0
a.length_squared() # 25
a.normalize()      # Vector2(0.6, 0.8); returns Vector2(0,0) if length==0
a.to_tuple()       # (3, 4)
x, y = a           # unpackable — Vector2/Vector3 are iterable

Vector2.zero()     # Vector2(0, 0)
Vector2.one()      # Vector2(1, 1)
```

`Vector3` mirrors all of the above, plus a true 3D `cross()`. `Vector2` has
no `z`; its `cross()` returns the scalar "which side is `other` on"
(positive/negative tells you rotation direction relative to `self`).

Both are used as **mutable** value objects throughout the engine — e.g.
`Collision`'s bounce resolution does `a.owner.position += normal * penetration`
and mutates `velocity` in place — so treat a `Vector2`/`Vector3` you hand to
the engine (like `actor.velocity`) as something that may be modified, not a
frozen snapshot.

## `Color`

`r, g, b, a` as ints in `0-255` (default `a=255`, fully opaque). Built to
match exactly what `mlx` wants on the wire:

```python
c = Color(255, 0, 0)          # opaque red
c.to_argb()                    # 0xFFFF0000 — packed int, mlx_pixel_put() format
c.to_bytes()                   # 4 little-endian bytes — same layout as
                                # what mlx_get_data_addr()'s buffer holds
Color.from_argb(0xFFFF0000)    # Color(255, 0, 0, 255)
c.to_floats()                  # (1.0, 0.0, 0.0, 1.0)

Color.white()
Color.black()
Color.transparent()
Color.magenta()                 # the classic "missing texture" color
```

If you're writing your own draw code that touches the framebuffer or a
`Texture`'s raw `.data`, `to_argb()` / `to_bytes()` / `from_argb()` are the
bridge between a `Color` and the raw pixel values the renderer/mlx expect
(0xAARRGGBB, little-endian).

## `Euler` & `Quaternion`

`Euler` stores a rotation as `pitch` (around X), `yaw` (around Y), `roll`
(around Z), in **radians**. It's meant as a human-readable/editable form —
for combining rotations or rotating vectors, convert to a `Quaternion`
first, since chained Euler angles are order-dependent and prone to gimbal
lock.

```python
e = Euler.from_degrees(pitch=0, yaw=90, roll=0)
e.to_degrees()          # (0.0, 90.0, 0.0)
q = e.to_quaternion()   # pitch(X) -> yaw(Y) -> roll(Z) intrinsic order
Euler.zero()
```

`Quaternion` is `w + xi + yj + zk`; identity (no rotation) is `Quaternion()`
(`w=1, x=y=z=0`).

```python
q1 = Quaternion.from_axis_angle(Vector3(0, 1, 0), math.radians(90))
q2 = Quaternion.identity()

q1 * q2            # Quaternion * Quaternion = combined rotation
                    # (applies `other` first, then self)
q1 * Vector3(1,0,0) # Quaternion * Vector3 = that vector rotated by q1

q1.conjugate()
q1.length()
q1.normalize()       # returns Quaternion() if length is 0
q1.to_euler()         # radians; clamps at the gimbal-lock singularity
```

Since 2D games (the shipped example is Pac-Man-style) rarely need real 3D
rotation, `Quaternion`/`Euler`/`Vector3` mostly exist for engine
completeness/future 3D work — day-to-day 2D gameplay code will mostly touch
`Vector2` and the `float` `rotation` degrees property on `AActor`.

## `enums.py`

Currently an empty placeholder in the shipped source — no engine-wide enums
(input keys, collision layers, asset types, etc.) have been defined yet.
Add your own and wire them into `Engine/Types/__init__.py`'s imports/`__all__`
if you want project-specific enums available from `Engine` directly.
