import ctypes
import numpy as np
from typing import Any
from mlx import Mlx
import math
from .. import Assets
from .. import Log, log_timing


class RendererSubsystem:
    """Owns mlx_init(), the window and the render framebuffer."""

    def __init__(self):
        self.mlx = None
        self.mlx_ptr = None
        self.win_ptr = None

        self.framebuffer = None
        self.framebuffer_data = None
        self.framebuffer_ptr = None

        self.width = 0
        self.height = 0
        self.title = "PacEngine"

        self.bpp = 0
        self.line_size = 0
        self.pixel_size = 0
        self.format = 0

        self.buffer = None
        self.buffer_size = 0
        self.buffer_np = None        # numpy view over self.buffer, shape (height, line_size)
        self._buffer_cbuf = None     # cached ctypes buffer for memmove (built once, not per frame)
        self._clear_view = None      # buffer reinterpreted as whole pixels, for one-shot clear()

        self.bake_buffer = None      # baked static-actor background, same layout as self.buffer
        self.bake_np = None          # numpy view over bake_buffer
        self._baked = False
        self._last_bake_world = None            # world passed to the last bake() call, if any
        self._last_bake_background_color = 0xFF000000

        self._scale_cache = {}       # (id(texture), scaled_w, scaled_h) -> resampled numpy array
        self._resize_listeners = []  # callbacks notified with (win_ptr, width, height) after resize()

        self._logger = Log.get("renderer")
        self._frame_count = 0

    def init(self, width: int, height: int, title: str = "PacEngine"):
        """Call once, at startup, before anything else touches mlx."""

        self.width = width
        self.height = height
        self.title = title

        self.mlx = Mlx()
        self.mlx_ptr = self.mlx.mlx_init()

        if self.mlx_ptr is None:
            raise RuntimeError("mlx_init() failed — no display available.")

        self.win_ptr = self.mlx.mlx_new_window(
            self.mlx_ptr, width, height, title
        )

        if self.win_ptr is None:
            raise RuntimeError("mlx_new_window() failed.")

        self.framebuffer = self.mlx.mlx_new_image(
            self.mlx_ptr, width, height
        )

        if self.framebuffer is None:
            raise RuntimeError("mlx_new_image() failed.")

        (
            self.framebuffer_data,
            self.bpp,
            self.line_size,
            self.format
        ) = self.mlx.mlx_get_data_addr(self.framebuffer)

        self.pixel_size = self.bpp // 8
        self.framebuffer_ptr = ctypes.addressof(self.framebuffer_data.obj)
        self.buffer_size = self.height * self.line_size
        self.buffer = bytearray(self.buffer_size)

        # Zero-copy numpy view over self.buffer. Writes to buffer_np land
        # directly in self.buffer's memory — no extra copy anywhere.
        self.buffer_np = np.frombuffer(self.buffer, dtype=np.uint8).reshape(
            self.height, self.line_size
        )

        # Built once instead of re-wrapping self.buffer every render() call.
        self._buffer_cbuf = (ctypes.c_char * self.buffer_size).from_buffer(self.buffer)

        # Reinterpret the buffer as whole pixels (not individual bytes) so
        # clear() can assign a color to the entire framebuffer in one
        # vectorized call instead of building/tiling a row per clear.
        pixel_dtype = {1: np.uint8, 2: np.uint16, 4: np.uint32}.get(self.pixel_size)
        if pixel_dtype is not None and self.line_size % self.pixel_size == 0:
            self._clear_view = self.buffer_np.view(dtype=pixel_dtype)
        else:
            # Unusual pixel size (e.g. 3 bytes/pixel) — clear() falls back
            # to the tiled-row approach below.
            self._clear_view = None

        self._logger.debug(
            f"Framebuffer info: bpp={self.bpp}, line_size={self.line_size}, "
            f"format={self.format}, pixel_size={self.pixel_size}"
        )

        Assets.init(self.mlx, self.mlx_ptr)

        self.mlx.mlx_hook(
            self.win_ptr, 33, 0, self._close_window, self
        )

        self._logger.info(f'Window created: {width}x{height} "{title}"')

        # Clear with FULLY OPAQUE BLACK
        self.clear(0xFF000000)

    def _get_component_position(self, component):
        """Get the world position of a component (actor position + local offset)."""
        if hasattr(component, 'get_world_position'):
            return component.get_world_position()
        # Fallback for components without local offset support
        actor = getattr(component, 'actor', None)
        if actor is not None:
            return (actor.position.x, actor.position.y)
        return (0.0, 0.0)

    def _sprite_for(self, actor):
        """Find the actor's current sprite by checking its
        components. Actors no longer carry a sprite directly —
        SpriteComponent and AnimatedSpriteComponent (Engine.Components)
        both expose a `.sprite` property, so this just looks for the
        first component that has one and returns whatever it's
        currently resolving to (None if that component's asset
        hasn't finished loading yet).

        Duck-typed on purpose (checks `hasattr(component, "sprite")`
        rather than isinstance against SpriteComponent /
        AnimatedSpriteComponent) so any future component that wants
        to be drawn just needs to expose `.sprite` — no changes
        needed here."""
        out_components: list[Any] = []

        components = getattr(actor, "components", None)
        if not components:
            return None

        for component in components:
            if hasattr(component, "sprite"):
                out_components.append(component)
        return out_components

    def _fill_solid(self, color: int):
        """One-shot solid color fill — the actual pixel-writing work.
        Used by clear() when there's no baked background, and by
        bake() itself to paint the initial background before drawing
        static actors onto it."""

        if self._clear_view is not None:
            pixel_value = color & ((1 << (self.pixel_size * 8)) - 1)
            self._clear_view[:, :self.width] = pixel_value
            return

        # Fallback for unusual pixel sizes that don't evenly divide
        # line_size (see init()).
        pixel_bytes = np.frombuffer(
            color.to_bytes(self.pixel_size, "little"), dtype=np.uint8
        )
        row = np.tile(pixel_bytes, self.width)
        if len(row) < self.line_size:
            row = np.concatenate(
                [row, np.zeros(self.line_size - len(row), dtype=np.uint8)]
            )
        self.buffer_np[:, :] = row

    def clear(self, color: int = 0xFF000000):
        """Clears the framebuffer before drawing the next frame.

        If bake() has been called, this copies the baked static-actor
        background in one vectorized operation instead of filling a
        solid color — `color` is ignored in that case, since the
        baked image already has its own background baked in.

        Without a bake, falls back to a single vectorized whole-pixel
        fill (see _fill_solid)."""

        if self._baked:
            self.buffer_np[:, :] = self.bake_np
            return

        self._fill_solid(color)

    def bake(self, world, background_color: int = 0xFF000000,
             max_wait_ticks: int = 300):
        """Pre-renders every static actor once into an internal
        background buffer. Call this after all static actors have
        been spawned — typically right before entering the main loop.

        From then on, clear() copies this baked image in a single
        buffer copy instead of re-blitting every static actor's
        sprite every single frame. render() also skips static actors
        in its per-frame draw loop, since they're already part of the
        baked background.

        An actor counts as static if `getattr(actor, "static", False)`
        is True — add a `static` attribute/flag to your Actor class
        (or subclasses) to opt in.

        Sprite assets resolve asynchronously (see _sprite_for) — a
        component's `.sprite` is None until its asset has finished
        loading. Since bake() only runs once, calling it before the
        assets are ready would silently skip those actors and leave
        a blank/solid-color background forever. To avoid that, bake()
        pumps Assets.update() (up to `max_wait_ticks` times) until
        every static actor's sprite components have resolved, or
        gives up and bakes anyway with a warning.

        Call bake() again (e.g. after spawning/removing static actors)
        to rebuild the background; call unbake() to go back to a
        plain solid-color clear()."""

        self._last_bake_world = world
        self._last_bake_background_color = background_color

        # Build directly into the main buffer as scratch — bypass the
        # baked shortcut in clear() while we're constructing the bake.
        self._baked = False
        self._fill_solid(background_color)

        static_actors = [a for a in world if getattr(a, "static", False)]

        def _sprites_pending() -> bool:
            for actor in static_actors:
                components = self._sprite_for(actor)
                if not components:
                    continue
                for component in components:
                    if getattr(component, 'sprite', None) is None:
                        return True
            return False

        ticks = 0
        while _sprites_pending() and ticks < max_wait_ticks:
            Assets.update()
            ticks += 1
        if ticks >= max_wait_ticks and _sprites_pending():
            self._logger.warning(
                "bake(): some static actor sprite(s) hadn't finished "
                f"loading after {max_wait_ticks} Assets.update() tick(s); "
                "baking anyway — those actors may be missing from the "
                "baked background."
            )

        for actor in static_actors:
            components = self._sprite_for(actor)
            if components is None:
                continue
            for component in components:
                sprite = getattr(component, 'sprite', None)
                if sprite is None:
                    continue
                try:
                    rotation = getattr(actor, 'rotation', 0.0)
                    component_rotation = getattr(component, 'local_rotation', 0.0)
                    pivot = getattr(actor, 'pivot', (0.5, 0.5))
                    position = self._get_component_position(component)
                    # Create a position object with x,y attributes
                    pos = type('Position', (), {'x': position[0], 'y': position[1]})()
                    self.draw_sprite(sprite, pos, actor.scale, rotation + component_rotation, pivot)
                except Exception:
                    self._logger.exception(f"Failed to bake actor {actor!r}")

        if self.bake_buffer is None:
            self.bake_buffer = bytearray(self.buffer_size)
            self.bake_np = np.frombuffer(self.bake_buffer, dtype=np.uint8).reshape(
                self.height, self.line_size
            )

        self.bake_np[:, :] = self.buffer_np
        self._baked = True

        self._logger.info(
            f"Baked {len(static_actors)} static actor(s) into background."
        )

    def unbake(self):
        """Reverts to a plain solid-color clear() instead of the
        baked background. The baked buffer itself is kept around
        (not freed) so a later bake() call is cheap to redo."""

        self._baked = False

    def put_pixel(self, x: int, y: int, color: int):
        """Writes a pixel directly into the framebuffer."""

        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return

        offset = x * self.pixel_size
        self.buffer_np[y, offset:offset + self.pixel_size] = np.frombuffer(
            color.to_bytes(self.pixel_size, "little"), dtype=np.uint8
        )

    def draw_rect(self, x, y, width, height, color: int):
        """Fill an axis-aligned rect with a solid 0xAARRGGBB color,
        alpha-blending against whatever's already in the framebuffer
        when color isn't fully opaque (same blend math as sprite
        drawing, just for a flat color instead of a texture).

        Meant for cheap effects that don't need a real texture — see
        ParticleSubsystem, which draws every particle this way
        instead of loading/blitting a sprite per particle."""

        x, y = int(x), int(y)
        width, height = int(width), int(height)

        if width <= 0 or height <= 0:
            return

        clip_x0 = max(0, -x)
        clip_y0 = max(0, -y)
        x = max(0, x)
        y = max(0, y)

        dw = min(width - clip_x0, self.width - x)
        dh = min(height - clip_y0, self.height - y)

        if dw <= 0 or dh <= 0:
            return

        dest_view = self.buffer_np[
            y:y + dh,
            x * self.pixel_size: (x + dw) * self.pixel_size,
        ].reshape(dh, dw, self.pixel_size)

        pixel_bytes = np.frombuffer(
            color.to_bytes(self.pixel_size, "little"), dtype=np.uint8
        )

        alpha = (color >> 24) & 0xFF if self.pixel_size == 4 else 255

        if alpha == 0:
            return

        if alpha == 255:
            dest_view[:, :, :] = pixel_bytes
            return

        a = np.uint16(alpha)
        src = pixel_bytes.astype(np.uint16)
        blended = (src * a + dest_view.astype(np.uint16) * (255 - a)) // 255
        blended[..., 3] = 255
        dest_view[:, :, :] = blended.astype(np.uint8)

    def draw_sprite(self, texture, position, scale, rotation=0.0, pivot=(0.5, 0.5)):
        """Draws a texture into the framebuffer with scaling and rotation support."""

        if hasattr(scale, 'x') and hasattr(scale, 'y'):
            scale_x = scale.x
            scale_y = scale.y
        else:
            scale_x = float(scale)
            scale_y = float(scale)

        dest_x = int(position.x)
        dest_y = int(position.y)

        scaled_width = max(1, int(texture.width * scale_x))
        scaled_height = max(1, int(texture.height * scale_y))

        if scaled_width <= 0 or scaled_height <= 0:
            return

        # Use rotation if specified (with small epsilon to avoid unnecessary work)
        if abs(rotation) > 0.001:
            self._blit_rotated(texture, dest_x, dest_y, rotation,
                            pivot[0], pivot[1], scaled_width, scaled_height)
        elif scale_x == 1.0 and scale_y == 1.0:
            self._blit(texture, dest_x, dest_y)
        else:
            self._blit(texture, dest_x, dest_y, scaled_width, scaled_height)

    @staticmethod
    def _get_texture_array(texture):
        """Returns a numpy (H, W, bpp) view over texture.data, cached on
        the texture itself. Textures are immutable after load, so this
        is safe to build once and reuse across every draw call/frame."""

        cached = getattr(texture, "_np_cache", None)
        if cached is not None:
            return cached

        raw = np.frombuffer(texture.data, dtype=np.uint8)
        raw = raw[: texture.line_size * texture.height].reshape(
            texture.height, texture.line_size
        )
        arr = raw[:, : texture.width * texture.bytes_per_pixel].reshape(
            texture.height, texture.width, texture.bytes_per_pixel
        )

        try:
            texture._np_cache = arr
        except AttributeError:
            pass

        return arr

    def _blit(self, texture, dest_x, dest_y, scaled_width=None, scaled_height=None):
        """Vectorized blit — replaces the old per-pixel draw_sprite /
        _draw_sprite_direct loops. Handles direct copy, nearest-neighbor
        scaling, and BGRA alpha blending, all as array ops."""

        tex = self._get_texture_array(texture)

        if scaled_width is None:
            region = tex
        else:
            # Same texture drawn at the same target size every frame
            # (the overwhelmingly common case — e.g. an actor with a
            # fixed scale) reuses the resampled array instead of
            # re-gathering it every call. Only actually re-resamples
            # the first time a given (texture, size) combo is seen.
            cache_key = (id(texture), scaled_width, scaled_height)
            region = self._scale_cache.get(cache_key)

            if region is None:
                src_ys = (np.arange(scaled_height) * texture.height // scaled_height)
                src_xs = (np.arange(scaled_width) * texture.width // scaled_width)
                src_ys = src_ys.clip(0, texture.height - 1)
                src_xs = src_xs.clip(0, texture.width - 1)
                region = tex[np.ix_(src_ys, src_xs)]
                self._scale_cache[cache_key] = region

        src_h, src_w = region.shape[0], region.shape[1]

        # Clip against screen bounds
        clip_x0, clip_y0 = 0, 0
        clip_x1, clip_y1 = src_w, src_h

        if dest_x < 0:
            clip_x0 = -dest_x
            dest_x = 0
        if dest_y < 0:
            clip_y0 = -dest_y
            dest_y = 0
        if dest_x + (clip_x1 - clip_x0) > self.width:
            clip_x1 = clip_x0 + (self.width - dest_x)
        if dest_y + (clip_y1 - clip_y0) > self.height:
            clip_y1 = clip_y0 + (self.height - dest_y)

        if clip_x1 <= clip_x0 or clip_y1 <= clip_y0:
            return  # fully off-screen

        region = region[clip_y0:clip_y1, clip_x0:clip_x1]
        dh, dw = region.shape[0], region.shape[1]

        dest_view = self.buffer_np[
            dest_y:dest_y + dh,
            dest_x * self.pixel_size: (dest_x + dw) * self.pixel_size,
        ].reshape(dh, dw, self.pixel_size)

        if texture.bytes_per_pixel == 4 and self.pixel_size == 4:
            alpha = region[:, :, 3]

            opaque_mask = alpha == 255
            transparent_mask = alpha == 0
            fully_opaque = opaque_mask.all()
            fully_transparent = transparent_mask.all()

            # Fast paths cover the overwhelmingly common cases: sprites
            # with hard-edged transparency (no soft/antialiased alpha).
            if fully_transparent:
                return
            if fully_opaque:
                dest_view[:, :, :] = region
                return

            blend_mask = ~(opaque_mask | transparent_mask)
            if not blend_mask.any():
                # Mixed opaque/transparent, but no partial-alpha pixels —
                # skip the blend math entirely.
                dest_view[opaque_mask] = region[opaque_mask]
                return

            # General path: real alpha blending where needed.
            a = alpha.astype(np.uint16)[:, :, None]
            blended = (
                region[:, :, :4].astype(np.uint16) * a
                + dest_view.astype(np.uint16) * (255 - a)
            ) // 255
            blended[:, :, 3] = 255

            dest_view[~transparent_mask] = blended[~transparent_mask].astype(np.uint8)
            dest_view[opaque_mask] = region[opaque_mask]
        else:
            # No alpha channel — straight copy.
            dest_view[:, :, :] = region[:, :, :self.pixel_size]

    def _blit_rotated(self, texture, dest_x, dest_y, angle_degrees,
                      pivot_x=0.5, pivot_y=0.5, scaled_width=None, scaled_height=None):
        """Vectorized blit with rotation support using nearest-neighbor rotation."""

        tex = self._get_texture_array(texture)
        src_h, src_w = tex.shape[0], tex.shape[1]

        # Determine target size
        if scaled_width is None:
            scaled_width = src_w
        if scaled_height is None:
            scaled_height = src_h

        # Pre-compute cos/sin once
        angle_rad = math.radians(angle_degrees)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Create output grid
        y_coords, x_coords = np.mgrid[0:scaled_height, 0:scaled_width]

        # Translate to pivot space (center of rotation)
        pivot_x = pivot_x * scaled_width
        pivot_y = pivot_y * scaled_height

        # Rotate coordinates around pivot
        x_rel = x_coords - pivot_x
        y_rel = y_coords - pivot_y

        src_x = (x_rel * cos_a + y_rel * sin_a + pivot_x) * (src_w / scaled_width)
        src_y = (-x_rel * sin_a + y_rel * cos_a + pivot_y) * (src_h / scaled_height)

        # Clip to texture bounds
        src_x = np.clip(src_x, 0, src_w - 1).astype(np.int32)
        src_y = np.clip(src_y, 0, src_h - 1).astype(np.int32)

        # Sample the texture
        region = tex[src_y, src_x]

        # Now blit this region like in _blit
        return self._blit_region(region, dest_x, dest_y,
                                scaled_width, scaled_height, texture.bytes_per_pixel)

    def _blit_region(self, region, dest_x, dest_y, region_w, region_h, bpp):
        """Internal method to blit a pre-processed region."""
        # Similar to the clipping/alpha blending code from _blit
        clip_x0, clip_y0 = 0, 0
        clip_x1, clip_y1 = region_w, region_h

        if dest_x < 0:
            clip_x0 = -dest_x
            dest_x = 0
        if dest_y < 0:
            clip_y0 = -dest_y
            dest_y = 0
        if dest_x + (clip_x1 - clip_x0) > self.width:
            clip_x1 = clip_x0 + (self.width - dest_x)
        if dest_y + (clip_y1 - clip_y0) > self.height:
            clip_y1 = clip_y0 + (self.height - dest_y)

        if clip_x1 <= clip_x0 or clip_y1 <= clip_y0:
            return

        region = region[clip_y0:clip_y1, clip_x0:clip_x1]
        dh, dw = region.shape[0], region.shape[1]

        dest_view = self.buffer_np[
            dest_y:dest_y + dh,
            dest_x * self.pixel_size: (dest_x + dw) * self.pixel_size,
        ].reshape(dh, dw, self.pixel_size)

        # Alpha blending (same as _blit)
        if bpp == 4 and self.pixel_size == 4:
            alpha = region[:, :, 3]

            opaque_mask = alpha == 255
            transparent_mask = alpha == 0
            fully_opaque = opaque_mask.all()
            fully_transparent = transparent_mask.all()

            if fully_transparent:
                return
            if fully_opaque:
                dest_view[:, :, :] = region
                return

            blend_mask = ~(opaque_mask | transparent_mask)
            if not blend_mask.any():
                dest_view[opaque_mask] = region[opaque_mask]
                return

            a = alpha.astype(np.uint16)[:, :, None]
            blended = (
                region[:, :, :4].astype(np.uint16) * a
                + dest_view.astype(np.uint16) * (255 - a)
            ) // 255
            blended[:, :, 3] = 255

            dest_view[~transparent_mask] = blended[~transparent_mask].astype(np.uint8)
            dest_view[opaque_mask] = region[opaque_mask]
        else:
            dest_view[:, :, :] = region[:, :, :self.pixel_size]

    def render_draw(self, world):
        """Draw all actors into the framebuffer (no presentation)."""
        if self.win_ptr is None:
            raise RuntimeError("RendererSubsystem.render_draw() called before .init().")

        # Clear with FULLY OPAQUE BLACK — or, if bake() has been called,
        # copies the baked static-actor background instead.
        self.clear(0xFFAAAAAA)

        # Draw all actors in order (later actors will overwrite earlier ones)
        for actor in world:
            if self._baked and getattr(actor, "static", False):
                continue

            components = self._sprite_for(actor)
            if components is None:
                continue
            for component in components:
                sprite = getattr(component, 'sprite', None)
                if sprite is None:
                    continue

                try:
                    rotation = getattr(actor, 'rotation', 0.0)
                    pivot = getattr(actor, 'pivot', (0.5, 0.5))
                    component_rotation = getattr(component, 'local_rotation', 0.0)
                    position = self._get_component_position(component)
                    # Create a position object with x,y attributes
                    pos = type('Position', (), {'x': position[0], 'y': position[1]})()
                    self.draw_sprite(
                        sprite,
                        pos,
                        actor.scale,
                        rotation + component_rotation,
                        pivot
                    )
                except Exception:
                    self._logger.exception(f"Failed to draw actor {actor!r}")

    def render_present(self):
        """Present the framebuffer to the screen."""
        if self.win_ptr is None:
            raise RuntimeError("RendererSubsystem.render_present() called before .init().")

        # Copy our buffer to the framebuffer (cached ctypes wrapper, no per-frame allocation)
        ctypes.memmove(
            self.framebuffer_ptr,
            ctypes.addressof(self._buffer_cbuf),
            self.buffer_size
        )

        # Present the framebuffer to the window
        self.mlx.mlx_put_image_to_window(
            self.mlx_ptr,
            self.win_ptr,
            self.framebuffer,
            0,
            0,
        )

    def render(self, world):
        """Legacy method - draws and presents in one call."""
        self.render_draw(world)
        self.render_present()

    def hook_loop(self, callback, param=None):
        """Registers `callback` to run once per mlx event-loop tick."""
        self.mlx.mlx_loop_hook(self.mlx_ptr, callback, param)

    def hook_close(self, callback, param=None):
        """Registers a custom close callback."""
        self.mlx.mlx_hook(self.win_ptr, 33, 0, callback, param)

    def _close_window(self, param):
        """Default window close handler."""
        self._logger.info("Window close requested.")
        self.mlx.mlx_loop_exit(self.mlx_ptr)

    def loop(self):
        """Starts the mlx event loop."""
        self._logger.info("Starting MLX event loop...")
        result = self.mlx.mlx_loop(self.mlx_ptr)
        self._logger.info(f"MLX event loop exited with: {result}")

    def close(self):
        """Destroys the window."""
        if self.win_ptr is not None:
            self.mlx.mlx_destroy_window(self.mlx_ptr, self.win_ptr)
            self.win_ptr = None

    def close_request(self):
        """Request the MLX loop to exit."""

        self._logger.info("Quit requested.")

        if self.mlx_ptr is not None:
            self.mlx.mlx_loop_exit(
                self.mlx_ptr
            )

    def on_resize(self, callback):
        """Register a callback to be notified after resize() rebuilds
        the window. Called as callback(win_ptr, width, height) with
        the *new* window pointer — use this to rebind anything that
        hooked mlx_hook() onto the old win_ptr directly (e.g. Input's
        key/mouse hooks), since that window is destroyed by resize()
        and takes its hooks with it. Without rebinding, the engine
        keeps running fine (the frame loop is hooked to mlx_ptr, not
        the window) but input will silently stop responding."""
        self._resize_listeners.append(callback)

    def resize(self, width: int, height: int, title: str = None):
        """Resize the window and framebuffer to a new width/height.

        Destroys the current native window and rebuilds it (and the
        framebuffer image + all buffers) at the new size — mirrors
        the buffer-setup steps in init(), just without re-running
        mlx_init(). If bake() had been called, the old baked background
        no longer matches the new size, so it's dropped and immediately
        rebuilt at the new dimensions from the same world/background_color
        used last time — no need to call bake() again yourself. If a
        static actor was added or removed via a normal bake() call in
        between, that's still what gets rebaked here, since we just
        re-run bake() with whatever world reference was last given."""

        if self.win_ptr is None:
            raise RuntimeError("RendererSubsystem.resize() called before .init().")

        if title is None:
            title = self.title

        self.close()  # destroys the old window (self.win_ptr -> None)

        self.width = width
        self.height = height
        self.title = title

        self.win_ptr = self.mlx.mlx_new_window(
            self.mlx_ptr, width, height, title
        )

        if self.win_ptr is None:
            raise RuntimeError("mlx_new_window() failed during resize().")

        self.framebuffer = self.mlx.mlx_new_image(
            self.mlx_ptr, width, height
        )

        if self.framebuffer is None:
            raise RuntimeError("mlx_new_image() failed during resize().")

        (
            self.framebuffer_data,
            self.bpp,
            self.line_size,
            self.format
        ) = self.mlx.mlx_get_data_addr(self.framebuffer)

        self.pixel_size = self.bpp // 8
        self.framebuffer_ptr = ctypes.addressof(self.framebuffer_data.obj)
        self.buffer_size = self.height * self.line_size
        self.buffer = bytearray(self.buffer_size)

        self.buffer_np = np.frombuffer(self.buffer, dtype=np.uint8).reshape(
            self.height, self.line_size
        )
        self._buffer_cbuf = (ctypes.c_char * self.buffer_size).from_buffer(self.buffer)

        pixel_dtype = {1: np.uint8, 2: np.uint16, 4: np.uint32}.get(self.pixel_size)
        if pixel_dtype is not None and self.line_size % self.pixel_size == 0:
            self._clear_view = self.buffer_np.view(dtype=pixel_dtype)
        else:
            self._clear_view = None

        # Old bake buffer is the wrong size for the new dimensions — drop
        # it, then immediately rebake from the last world/color passed to
        # bake() (if any) so callers don't have to remember to redo it
        # after every resize. Falls back to a solid fill on the next
        # clear() if bake() was never called in the first place.
        self._baked = False
        self.bake_buffer = None
        self.bake_np = None

        if self._last_bake_world is not None:
            try:
                self.bake(self._last_bake_world, self._last_bake_background_color)
            except Exception:
                self._logger.exception("Failed to rebake background after resize")

        self.mlx.mlx_hook(
            self.win_ptr, 33, 0, self._close_window, self
        )

        self._logger.info(f'Window resized: {width}x{height} "{title}"')

        self.clear(0xFF000000)

        # Let anything bound to the old win_ptr (e.g. Input's key/mouse
        # hooks) rebind itself against the new one.
        for listener in self._resize_listeners:
            try:
                listener(self.win_ptr, width, height)
            except Exception:
                self._logger.exception("resize listener failed")


# Global renderer system
Renderer = RendererSubsystem()
