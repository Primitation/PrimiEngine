# Getting Started

## Requirements

- Python 3.10+ (uses `from __future__ import annotations`, dataclasses, etc.)
- `numpy`
- A working `mlx` (minilibx) Python binding exposing `Mlx()`, importable as
  `from mlx import Mlx`
- An X11 display available for `mlx_init()` to connect to

## Boot order

The engine is a collection of global singletons that must be wired together
in a specific order, because several of them depend on state that only
exists once an earlier one has finished initializing:

1. **`Renderer.init(width, height, title)`** — calls `mlx_init()`, opens the
   window, creates the framebuffer, and (as a side effect) calls
   `Assets.init(mlx, mlx_ptr)` for you.
2. **`Collision.init(width, height)`** — without this, boundary resolution
   (clamping actors to the screen edges) is silently disabled.
3. **`Input.init(Renderer)`** — must happen *after* `Renderer.init()`, since
   it reads `renderer.mlx`, `renderer.mlx_ptr`, and `renderer.win_ptr`.
4. Spawn your actors (directly, or via a `Level`, see
   [10 - Full Example](10-full-example.md)).
5. Optionally call `Renderer.bake(World)` once all your static (background)
   actors are spawned, to avoid re-blitting them every frame — see
   [04 - Rendering](04-rendering.md).
6. Enter your main loop.

## Minimal runnable example

```python
from Engine import (
    Renderer, Collision, Input, Actors, World,
    Particles, AActor, Vector2, SpriteComponent,
)

WIDTH, HEIGHT = 800, 600

def main():
    Renderer.init(WIDTH, HEIGHT, "My Game")
    Collision.init(WIDTH, HEIGHT)
    Input.init(Renderer)

    class Wall(AActor):
        def __init__(self, position):
            super().__init__(position=position, scale=Vector2(1, 1), static=True)
            self.add_component(SpriteComponent("assets/texture/wall.png"))

    Actors.spawn(Wall, position=Vector2(100, 100))

    # Bake static actors into the background once they're all spawned.
    Renderer.bake(World)

    def frame(_param=None):
        dt = 16.0  # milliseconds; swap in a real clock for variable dt

        Assets.update()
        Input.process_events()
        Input.update()
        Input.process_actions()

        Actors.update(dt)
        Collision.update()

        Renderer.render_draw(World)
        Particles.update(dt)
        Particles.render(Renderer)
        Renderer.render_present()

    Renderer.hook_loop(frame)
    Renderer.loop()  # blocks, runs the mlx event loop

if __name__ == "__main__":
    main()
```

A few things worth noting from this example:

- `Renderer.hook_loop(callback)` registers `callback` to run once per mlx
  event-loop tick — this is where your per-frame update/render code goes.
  `Renderer.loop()` then blocks and drives that loop.
- `Actors.spawn(ActorClass, **kwargs)` is the standard way to create and
  register an actor — it also adds it to `World` for you (unlike calling
  `ActorClass(...)` directly, which registers it with `Actors` but *not*
  `World`; prefer `Actors.spawn` in your own game code).
- Pressing **Escape** already quits by default — `Input` binds a `"quit"`
  action to Escape and wires it straight to `Renderer.close_request` during
  its own setup.

## Shutting down cleanly

When the mlx loop exits (window closed, or `Renderer.close_request()`
called), you may want to release resources:

```python
Input.close()      # restores OS key auto-repeat, stops the input thread
Renderer.close()    # destroys the mlx window
Log.close()         # flushes and closes the log file, stops the log thread
```
