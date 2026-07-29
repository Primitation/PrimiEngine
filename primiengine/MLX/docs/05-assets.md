# Assets

`Assets` (an instance of `AssetSubsystem`) is the global cache/loader for
everything that comes from disk — currently textures (PNG/XPM) and
sprite-sheet slices. **Assets are identified by their path**; the path *is*
the cache key, so two actors loading the same path automatically share the
same `Texture`. Gameplay code never deals in cache identifiers, only paths
(or `SpriteSheetKey` for sheets, described below).

## Setup

```python
Assets.init(mlx, mlx_ptr)
```

Called for you automatically by `Renderer.init()`. Do not call this
yourself unless you're bypassing `Renderer.init()` for some reason — it
must run once, right after `mlx_init()`, before anything loads or queues an
asset.

## Loading vs. queueing

```python
texture = Assets.load("assets/texture/pacman.png")   # BLOCKS until loaded
Assets.queue("assets/texture/pacman.png")              # non-blocking, async
```

- **`load(path)`** loads synchronously on the calling thread and returns the
  finished asset immediately. Fine for level-load-time work; avoid calling
  it inside a hot per-frame path.
- **`queue(path)`** is what `SpriteComponent`/`AnimatedSpriteComponent` use
  internally. It hands the path to a background worker thread; nothing
  useful comes back immediately — `Assets.get(path)` will keep returning
  `None` until it's ready. Queueing the same path multiple times (e.g. two
  actors both wanting `"pacman.png"`) is safe and free after the first
  call — already-cached or already-loading paths are ignored.

You **must** call `Assets.update()` once per frame (from the main thread)
for queued loads to ever complete — it drains the worker thread's finished
results and promotes them into the cache.

```python
Assets.update()                      # call every frame
Assets.get(path)                     # cached asset, or None if not ready
Assets.ready(path)  -> bool
Assets.loading(path) -> bool
Assets.cached(path)  -> bool
```

### Why the split main/worker-thread model

`mlx` talks to the X server through a single connection (`mlx_ptr`) and is
**not thread-safe** — every `mlx_*` call has to happen on the main thread.
So each `AssetLoader` splits work into:

- **`load(path)`** — runs on the **worker thread**. File I/O only, no
  `mlx_*` calls.
- **`finalize(raw)`** — runs on the **main thread**, once `load()` has
  returned. Anything that touches `mlx` (`mlx_png_file_to_image`,
  `mlx_new_image`, ...) belongs here.

For `TextureLoader`/`SpriteSheetLoader` specifically, mlx does its own PNG
decoding *inside* `mlx_png_file_to_image`, and that call has to happen on
the main thread regardless — so `load()` for these two loaders is a no-op
pass-through, and all the real work happens in `finalize()`.

## `Texture`

```python
class Texture:
    def __init__(self, img, width, height, data, bpp, line_size, endian): ...
```

Wraps a loaded mlx image plus its raw pixel buffer. The mlx `img` handle is
kept for direct mlx rendering if you ever need it; the raw `data` buffer is
what `Renderer` actually samples from for scaling/rotation/flipping — pixel
operations mlx itself doesn't provide. **Textures are immutable after
creation** — actors only ever reference a texture, they never mutate it.

## Static sprites: `TextureLoader`

Handles any path ending in `.png` or `.xpm` (the only two formats `mlx`
itself decodes — no jpg/bmp support). Registered by default in
`AssetSubsystem.__init__`, so you don't need to register it yourself.

```python
Assets.queue("assets/texture/pacman.png")
texture = Assets.get("assets/texture/pacman.png")   # Texture, or None
```

If loading fails (bad path, decode error), `Assets`/`AssetManager` logs the
error and falls back to `TextureLoader.placeholder()` — a hand-built
64x64 magenta/black checkerboard "missing texture" image — instead of
crashing or leaving the path stuck pending forever.

## Sprite sheets: `SpriteSheetLoader` & `SpriteSheetKey`

A sprite sheet is sliced into individual frame `Texture`s (left-to-right,
top-to-bottom), each a plain, ordinary `Texture` — so the renderer draws
animated sprites exactly like static ones.

```python
from Engine import SpriteSheetKey

key = SpriteSheetKey(
    path="assets/texture/spritesheets/pacman_hd/PacManAssets-PacMan.png",
    frame_width=32,
    frame_height=32,
    frame_count=4,      # None = every frame in the sheet
    columns=None,        # None = derive from sheet width // frame_width
    start_frame=0,        # row-major index of the first frame to slice
)
Assets.queue(key)
frames = Assets.get(key)   # list[Texture], or None until ready
```

`SpriteSheetKey` is a frozen/hashable `dataclass`, so it drops straight
into the same path-keyed cache/pending/loading dicts `AssetSubsystem`
already uses for plain string paths — anywhere those expect `path: str`, a
`SpriteSheetKey` works too. Two calls with identical fields share the same
sliced frames.

`start_frame` is what lets several animations (e.g. walk vs. death) or
several characters (e.g. each ghost color) share one sheet at different
offsets — it's the row-major index of the first frame to slice.

## `Animation`

A thin, cheap, actor-owned playback wrapper around a shared frame list —
multiple actors can play the *same* cached frames at their own independent
speed/loop settings without re-slicing anything:

```python
from Engine import Animation

anim = Animation(frames, fps=10.0, loop=True)
current = anim.frame_at(elapsed_ms)     # Texture or None
anim.finished(elapsed_ms)                # only meaningful when loop=False
```

In practice you rarely construct `Animation` yourself — `AnimatedSpriteComponent`
manages one internally (see [02 - Core Concepts](02-core-concepts.md) and
the `Components` docs there).

## Registering your own loader

To support a new asset type, subclass `AssetLoader`:

```python
from Engine.AssetSubsystem.loader import AssetLoader

class JsonDataLoader(AssetLoader):
    def can_load(self, path):
        return isinstance(path, str) and path.lower().endswith(".json")

    def load(self, path):
        import json
        with open(path) as f:
            return json.load(f)   # pure file I/O — safe off the main thread

    # no mlx calls needed here, so the default finalize()/placeholder()
    # (pass raw through, return None on failure) are already fine.

Assets.register(JsonDataLoader())
```

`AssetManager._find_loader` tries every registered loader's `can_load(path)`
in registration order and uses the first match; if none match, it logs an
error and raises `ValueError`. Register loaders that need to distinguish
similar-looking paths (e.g. two different `.json` schemas) more
specifically before a catch-all one.

## Sound

There is currently **no audio support** — `mlx` (minilibx) has no audio API
at all (`mlx.h` only covers windows/images/events/the X11 loop), so a
`SoundLoader` was deliberately left out rather than faked. The source
comments suggest two ways to add it back if needed:

1. Keep `pygame` around just for `pygame.mixer` audio, running alongside
   `mlx` for display — they don't conflict (mlx owns the window/X11
   connection, `pygame.mixer` only touches `SDL_audio`).
2. Use a dedicated audio library (e.g. `sounddevice`, `simpleaudio`) to drop
   the pygame dependency entirely.
