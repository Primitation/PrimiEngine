# Logging

`Log` (an instance of `LogSubsystem`) is a global, thread-safe, asynchronous
logger — messages are pushed onto a queue and formatted/printed/written by
a dedicated background thread, so logging from any thread (e.g. the asset
loader's worker thread) never blocks the caller.

## Getting a named logger

```python
from Engine import Log

logger = Log.get("player")   # or: Log.get(self.__class__.__name__)

logger.debug("spawned at (10, 20)")
logger.info("level loaded")
logger.success("save complete")
logger.warning("asset missing, using placeholder")
logger.error("failed to open save file")
logger.fatal("renderer context lost")
logger.exception("caught in update()")   # appends a formatted traceback
```

Every `AActor` already gets one for free: `self.logger` is set to
`Log.get(self.__class__.__name__)` in `AActor.__init__`.

Each log line is tagged with its logger name and rendered like:

```
[14:03:21] [--INFO---] [player] level loaded
```

Console output is colorized by level (grey=DEBUG, default=INFO,
green=SUCCESS, yellow=WARNING, red=ERROR, magenta=FATAL).

## Log levels & modes

```python
Log.verbose()   # LogMode.DEBUG   — everything
Log.normal()     # LogMode.RELEASE — INFO and above
Log.errors()      # LogMode.QUIET   — WARNING and above
```

Filtering happens at push-time (`Logger._allowed`) based on the current
mode, so a call below the current threshold is simply dropped rather than
queued and discarded later.

## Console / file output

```python
Log.enable_console()
Log.disable_console()

Log.enable_file("logs/latest.log")   # default path if you omit the argument
Log.disable_file()
```

A log file is created by default at construction time
(`file="logs/latest.log"` in `Logger.__init__`), and its parent directory
is created automatically if missing. Calling `enable_file()` again with a
different path swaps to a new file (closing the old one).

## Shutdown

```python
Log.close()
```

Stops the background worker thread cleanly (drains anything already queued
first) and closes the log file if one is open. Call this once, near the
end of your program, alongside `Renderer.close()`/`Input.close()`.

## `log_timing` — profiling decorator

```python
from Engine import log_timing

class RendererSubsystem:
    @log_timing(every=60)
    def render(self, world):
        ...
```

Wraps a method, timing each call. Rather than logging every single call
(noisy), it accumulates a running total and only logs the **average**
duration once every `every` calls (default `300`), then resets the
counters:

```
[14:03:21] [--DEBUG--] [renderer] render average took 1.204 ms (60 calls)
```

- **`label`** — what shows up in the log line; defaults to the wrapped
  method's own `__name__`.
- **`logger_attr`** — the attribute name on `self` holding a `Log` logger
  to write to (default `"_logger"` — matches the convention every
  subsystem in this engine already follows, e.g.
  `self._logger = Log.get("collision")`).
- **`every`** — how many calls to average over before logging and
  resetting.

This is used throughout the engine's own subsystems — e.g.
`CollisionSubsystem.update()` and `ParticleSubsystem.update()` are both
decorated with `@log_timing()` — as a lightweight, low-overhead way to spot
performance regressions without a full profiler.

## Notes

- All logging is fully asynchronous: a call like `logger.info(...)` just
  pushes a `LogMessage` dataclass (`logger`, `type`, `message`, `time`) onto
  a queue and returns immediately; the actual formatting/printing/file
  write happens later, off the calling thread.
- `NamedLogger.exception(message)` is meant to be called from an `except`
  block — it appends `traceback.format_exc()` to the message automatically,
  at `ERROR` level.
