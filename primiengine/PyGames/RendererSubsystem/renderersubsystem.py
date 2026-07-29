import threading
import pygame

from .renderer import Renderer


class RendererSubsystem:

    def __init__(self):

        self._renderer = None
        self._lock = threading.Lock()

        self._clock = pygame.time.Clock()
        self._fps = 60

        self._running = False
        self._thread = None

    def init(self, screen, fps: int = 60):
        """Call once, right after pygame.display.set_mode(), to hand
        the subsystem its screen and start the render thread."""

        self._renderer = Renderer(screen)
        self._fps = fps

        self._running = True

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def add(self, sprite, layer: int = 0):
        """Thread-safe: call this from wherever your game logic
        lives, it doesn't have to be the render thread."""

        with self._lock:
            self._renderer.add(sprite, layer)

    def _run(self):

        while self._running:

            with self._lock:
                self._renderer.screen.fill((120, 120, 120))
                self._renderer.render()

            self._clock.tick(self._fps)

    def present(self):
        """Call this once per frame from your MAIN thread to flip
        the display. Kept off the render thread on purpose — window
        calls aren't guaranteed thread-safe everywhere (notably
        macOS wants them on the main thread). The lock makes sure
        this never grabs a half-drawn frame."""

        with self._lock:
            pygame.display.flip()

    def close(self):

        self._running = False

        if self._thread:
            self._thread.join()


# Global renderer system
Render = RendererSubsystem()
