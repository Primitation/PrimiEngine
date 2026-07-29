# Rendering

`Renderer` (an instance of `RendererSubsystem`) owns `mlx_init()`, the
window, and a software framebuffer backed by a `numpy` array for fast
vectorized blitting. It does **not** know about `Actor`/`Component` types by
name — it duck-types, looking for any component exposing a `.sprite`
attribute (see `_sprite_for`), so any future component that wants to be
drawn just needs a `.sprite` property.

## Setup

```python
Renderer.init(width, height, title="PrimiEngine")
```

This calls `mlx_init()`, opens an `mlx_new_window`, allocates the
framebuffer, and — importantly — calls `Assets.init(mlx, mlx_ptr)` for you,
so you don't need to call that separately. It also clears the screen to
opaque black and registers a default window-close handler
(`mlx_loop_exit`) on the `DESTROY_NOTIFY` event.

## The frame

Per-frame you generally call, in order:

```python
Renderer.render_draw(world)   # draw everything into the framebuffer
Particles.update(dt)
Particles.render(Renderer)     # particles drawn into the *same* framebuffer
Renderer.render_present()      # copy framebuffer -> mlx image -> window
```

(`Renderer.render(world)` is a legacy convenience that just calls
`render_draw` then `render_present` back-to-back — use the split version if
you need particles or any other extra pass in between, like the example
above.)

`render_draw(world)`:
1. Clears the framebuffer (`clear()`, see baking below).
2. Iterates `world` in order — **later actors draw over earlier ones** —
   and for each one:
   - Skips it if it's `static` and a bake is active (see below).
   - Finds the first component with a `.sprite` attribute
     (`SpriteComponent` / `AnimatedSpriteComponent`).
   - Skips it if that sprite hasn't finished loading yet (`None`).
   - Draws it via `draw_sprite(sprite, position, actor.scale, actor.rotation, actor.pivot)`,
     where `position` comes from the component's own
     `get_world_position()` (so local offsets/rotation are respected).
   - Any exception while drawing a single actor is logged and the rest of
     the frame continues (`renderer._logger.exception(...)`), rather than
     crashing the whole render.

## Baking static backgrounds

If part of your scene never moves (walls, floor tiles, background art),
call `Renderer.bake(world)` once, after they're all spawned:

```python
Actors.spawn(Wall, position=Vector2(0, 0))
# ... spawn every other static actor ...
Renderer.bake(World)
```

`bake()`:
- Fills a background color, then draws every actor in `world` where
  `getattr(actor, "static", False)` is `True` into an internal buffer.
- Stores that buffer (`bake_buffer` / `bake_np`).
- From then on, `clear()` copies this baked image in one vectorized
  operation instead of re-blitting every static actor's sprite each frame,
  and `render_draw()` skips static actors entirely in its per-actor loop.

Call `Renderer.bake(world)` again any time you add/remove static actors, to
rebuild the background. Call `Renderer.unbake()` to go back to a plain
solid-color `clear()` (the baked buffer itself is kept around so a later
`bake()` is cheap).

```python
Renderer.unbake()
```

## Sprites, scaling & rotation

```python
Renderer.draw_sprite(texture, position, scale, rotation=0.0, pivot=(0.5, 0.5))
```

- `texture` — a `Texture` (see [05 - Assets](05-assets.md)).
- `position` — anything with `.x`/`.y` (an actor position, or a
  `get_world_position()` result wrapped as needed).
- `scale` — a `Vector2`-like object (`.x`/`.y`) or a plain float/int applied
  uniformly.
- `rotation` — degrees; rotation only kicks in above a small epsilon
  (`> 0.001`), otherwise the (cheaper) unrotated blit path is used.
- `pivot` — fraction of the sprite's own box, default center.

Internally this picks between three blit paths for performance:
- **Direct copy** — no scale, no rotation.
- **`_blit`** — vectorized nearest-neighbor scaling + alpha blending, with a
  resampled-region cache (`_scale_cache`) keyed on `(texture id, scaled
  width, scaled height)` so repeatedly drawing the same texture at the same
  size (the common case for a fixed-scale actor) doesn't re-resample every
  frame.
- **`_blit_rotated` / `_blit_region`** — nearest-neighbor rotation around a
  pivot, built from a coordinate grid (`np.mgrid`) rather than a per-pixel
  Python loop.

Alpha blending (when the texture has 4 bytes/pixel and the framebuffer does
too) has fast paths for fully-opaque and fully-transparent regions, falling
back to real per-pixel alpha blending only where some pixels are partially
transparent.

## Primitives

```python
Renderer.draw_rect(x, y, width, height, color)   # color: 0xAARRGGBB int
Renderer.put_pixel(x, y, color)
```

`draw_rect` alpha-blends against the existing framebuffer content when
`color`'s alpha isn't fully opaque — this is what `ParticleSubsystem` uses
to draw flat-colored particles cheaply, without needing a texture (see
[08 - Particles](08-particles.md)).

## mlx event loop integration

```python
Renderer.hook_loop(callback, param=None)  # runs once per mlx event-loop tick
Renderer.hook_close(callback, param=None)  # custom window-close handler
Renderer.loop()                             # blocks; runs mlx_loop()
Renderer.close()                            # destroys the window
Renderer.close_request()                    # asks the mlx loop to exit
```

`Input` also wires its own close callback (`Input.on_close(Renderer.close_request)`)
during its default setup, and binds Escape to `"quit"`, which is routed to
`Renderer.close_request` too — so a fresh project quits cleanly on window-X
or Escape without any extra code.
