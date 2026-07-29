# PacEngine Documentation

PacEngine is a small 2D game engine written in Python, built on top of
**minilibx (mlx)** for windowing/pixels and **numpy** for fast software
rendering. It follows an Actor/Component architecture (similar in spirit to
Unreal/Unity) with a set of global subsystems that own one concern each:
rendering, assets, actors, collision, particles, input, and logging.

This documentation is split into the following pages:

| Page | Contents |
|---|---|
| [01 - Getting Started](docs/01-getting-started.md) | Boot sequence, main loop, minimal runnable example |
| [02 - Core Concepts](docs/02-core-concepts.md) | `World`, `AActor`, `Component`, the Actor/Component model |
| [03 - Math & Types](docs/03-types.md) | `Vector2`, `Vector3`, `Quaternion`, `Euler`, `Color` |
| [04 - Rendering](docs/04-rendering.md) | `Renderer`, sprites, rotation, baking static backgrounds |
| [05 - Assets](docs/05-assets.md) | `Assets`, textures, sprite sheets, animations, custom loaders |
| [06 - Collision](docs/06-collision.md) | `Collision`, `ColliderComponent`, overlap events, blocking/bounce |
| [07 - Input](docs/07-input.md) | `Input`, actions, key/mouse queries, callbacks |
| [08 - Particles](docs/08-particles.md) | `Particles`, `Particle`, emitting bursts and trails |
| [09 - Logging](docs/09-logging.md) | `Log`, named loggers, log levels, `log_timing` |
| [10 - Full Example](docs/10-full-example.md) | A complete Pac-Man-style player, walked through top to bottom |

## Quick orientation

Everything you need is re-exported from the top-level `Engine` package:

```python
from Engine import (
    Log, log_timing,
    Assets, SpriteSheetKey, Animation,
    Actors, AActor, on_end_of_anim,
    Collision,
    SpriteComponent, AnimatedSpriteComponent, ColliderComponent, Component,
    ParticleSubsystem, Particle, Particles,
    Renderer,
    Vector2, Vector3, Quaternion, Euler, Color,
    World,
    Input,
)
```

Almost all of the engine's subsystems (`Log`, `Assets`, `Actors`, `Collision`,
`Renderer`, `Particles`, `Input`, `World`) are **singletons** — you import the
already-constructed instance and call methods on it directly, you never
instantiate the subsystem class yourself.

## Architecture at a glance

```
Renderer.init(width, height, title)     # creates the mlx window + framebuffer
Assets.init(mlx, mlx_ptr)                # (done automatically by Renderer.init)
Collision.init(width, height)            # world bounds for boundary resolution
Input.init(Renderer)                     # must come after Renderer.init()

# main loop, once per frame:
Assets.update()          # promote finished async loads into the cache
Input.process_events()   # drain queued OS input events
Input.update()            # roll PRESSED -> HELD, RELEASED -> IDLE
Input.process_actions()   # fire action callbacks
Actors.update(dt)         # tick every actor + its components
Collision.update()        # broad+narrow phase, resolve blocking, fire overlaps
Renderer.render_draw(world)
Particles.update(dt)
Particles.render(Renderer)
Renderer.render_present()
```

See [01 - Getting Started](01-getting-started.md) for a runnable version of
this loop.
