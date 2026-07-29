# Input

`Input` (an instance of `InputSubsystem`) wraps mlx/X11 key and mouse
events into a frame-stable state machine, plus an "action" layer for
rebindable input (`"jump"` bound to both Space and a gamepad button, for
example, though only keyboard/mouse are wired up currently).

## Setup

```python
Input.init(Renderer)   # must come AFTER Renderer.init()
```

`Input.init()` pulls `renderer.mlx`, `renderer.mlx_ptr`, `renderer.win_ptr`
off the already-initialized `Renderer`, disables OS key auto-repeat
(`mlx_do_key_autorepeatoff`) so held keys don't flicker between held/released
as the OS repeat-delay kicks in, registers mlx event hooks, and starts a
background input-processing thread.

It also sets up default action bindings and callbacks (see below), so a
fresh project immediately has WASD/arrow movement actions and a working
Escape-to-quit.

## Per-frame update

Call these once per frame, in this order:

```python
Input.process_events()    # drain queued input events into key/mouse state
Input.update()              # roll PRESSED -> HELD, RELEASED -> IDLE, reset wheel
Input.process_actions()     # fire any registered action callbacks
```

`process_events()` and `update()` are both required for input to work at
all in a frame-stable way — `process_events()` applies whatever the OS
reported since last frame, and `update()` is what turns a one-frame
`PRESSED` into a sticky `HELD` (and `RELEASED` into `IDLE`) so
`is_key_pressed()` only reads `True` on the exact frame the press happened.

## Key/mouse state queries

```python
Input.is_key_pressed(key)     # just pressed this frame
Input.is_key_held(key)         # pressed or held
Input.is_key_released(key)     # just released this frame
Input.is_key_down(key)          # currently down at all
Input.is_any_key_pressed([k1, k2])
Input.is_any_key_held([k1, k2])
Input.is_modifier_active("shift")   # "shift" / "ctrl" / "alt" / "meta"

Input.get_mouse_position()          # (x, y)
Input.is_mouse_button_pressed(MouseButton.LEFT)
Input.is_mouse_button_held(MouseButton.LEFT)
Input.is_mouse_button_released(MouseButton.LEFT)
Input.get_mouse_wheel()               # +1 / -1 / 0, reset every update()
```

Keys are referenced by their X11 keycode integer. `Input.KEYS` is a
name → keycode dict covering letters, digits, common keys (`space`, `tab`,
`enter`, `escape`, `backspace`, `delete`, `insert`), navigation
(`left/up/right/down`, `page_up/page_down`, `home/end`), modifiers
(`shift`/`ctrl`/`alt`/`meta` — left-side variants), and `f1`-`f12`:

```python
Input.KEYS["space"]        # 32
Input.KEYS["escape"]        # 65307
Input.get_key_name(65307)    # "escape"
```

## Actions (the recommended layer to build gameplay against)

Actions decouple gameplay code from specific keys, so rebinding later
doesn't touch gameplay logic:

```python
Input.bind_action("jump", [Input.KEYS["space"], Input.KEYS["up"]])
Input.bind_action_combo("save", [Input.KEYS["ctrl"], Input.KEYS["s"]])  # all keys must be held

Input.is_action_triggered("jump")   # just triggered this frame
Input.is_action_held("jump")         # currently held
Input.is_action_released("jump")     # just released this frame
```

- **`bind_action`** — any *one* of the given keys triggers the action.
- **`bind_action_combo`** — *all* keys in the combo must be held; the
  action triggers on the frame the *last* one lands (checked via
  `is_key_pressed` on any key in the combo while every key in it is
  currently held).

### Default actions set up by `Input.init()`

| Action | Keys |
|---|---|
| `quit` | Escape |
| `confirm` | Enter, Space |
| `cancel` | Escape |
| `up` | Up arrow, W |
| `down` | Down arrow, S |
| `left` | Left arrow, A |
| `right` | Right arrow, D |
| `pause` | P |

`quit` is additionally wired straight to `Renderer.close_request` via
`register_action_callback`, and `Input.on_close(Renderer.close_request)` is
also registered — so both an OS window-close and pressing Escape cleanly
exit the mlx loop out of the box.

### Action callbacks

```python
Input.register_action_callback("jump", player.do_jump)
```

Registered callbacks fire from `Input.process_actions()`, once per frame,
for every action whose `is_action_triggered()` is currently `True`.

## Direct key/mouse callbacks

If you'd rather react to raw events instead of polling per-frame state:

```python
Input.on_key_press(Input.KEYS["e"], lambda state, keycode: interact())
Input.on_key_release(Input.KEYS["e"], lambda state, keycode: stop_interact())
Input.on_any_key(lambda keycode, state: ...)

Input.on_mouse_click(MouseButton.LEFT, lambda state, x, y: shoot(x, y))
Input.on_any_mouse(lambda button, state, x, y: ...)

Input.on_close(lambda: print("window closing"))
```

## Recording & playback

```python
Input.start_recording()
# ... play normally ...
events = Input.stop_recording()          # list[InputEvent]
Input.play_recorded_input(events, callback)  # calls callback(event) for each
```

Useful for demo playback, deterministic replays, or automated testing of
input-driven behavior. `input_buffer` caps at `Input.buffer_size` (default
100) events, dropping the oldest once full.

## Debugging

```python
Input.get_active_keys()      # list of held key names, e.g. ["w", "space"]
Input.get_debug_info()        # multi-line string: active keys, modifiers, mouse
Input.clear_states()           # reset all key/mouse/modifier state
```

## Threading model

Under the hood, mlx event hooks push raw events onto a queue from
whichever thread mlx calls them on; a background thread
(`_input_worker`, best-effort real-time scheduled via `SCHED_FIFO` where
permitted) drains that queue and updates internal state continuously. This
is separate from `process_events()`, which drains events from the same
queue for the main-thread-facing update path used in the standard per-frame
loop. In the standard usage pattern shown above (`process_events()` +
`update()` + `process_actions()` each frame), you don't need to think about
the background thread directly — just remember `Input.close()` should be
called on shutdown to stop it and restore OS key auto-repeat.
