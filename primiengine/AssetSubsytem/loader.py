import pygame
import threading
import queue
import traceback
from abc import ABC, abstractmethod

from ..LogSubsytem import Log


class AssetLoader(ABC):
    """One loader per asset type. Same idea as your DataProcessor:
    the manager asks can_load() to pick the right one, then calls
    load()/finalize() on it."""

    @abstractmethod
    def can_load(self, path):
        pass

    @abstractmethod
    def load(self, path):
        """Runs on the WORKER thread. Keep this to file I/O and
        decoding only — no pygame surface/mixer calls here, SDL
        isn't safe to touch off the main thread."""
        pass

    def finalize(self, raw):
        """Runs on the MAIN thread, once load() has returned.
        Override this for anything that has to touch pygame's
        display or mixer (convert_alpha, Sound, etc)."""
        return raw


class TextureLoader(AssetLoader):

    def can_load(self, path):
        return path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))

    def load(self, path):
        return pygame.image.load(path)

    def finalize(self, raw):
        return raw.convert_alpha()


class SoundLoader(AssetLoader):

    def can_load(self, path):
        return path.lower().endswith((".wav", ".ogg", ".mp3"))

    def load(self, path):
        return path

    def finalize(self, raw):
        return pygame.mixer.Sound(raw)


class AssetManager:

    def __init__(self):

        self._loaders = []
        self._assets = {}
        self._pending = set()
        self._lock = threading.Lock()

        self._cache = {}            # path -> finalized asset
        self._path_pending = {}     # path -> list of names waiting on it

        self._logger = Log.get("assets")

        self._in_queue = queue.Queue()
        self._out_queue = queue.Queue()

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def register(self, loader):
        self._loaders.append(loader)

    def _find_loader(self, path):

        for loader in self._loaders:
            if loader.can_load(path):
                return loader

        self._logger.error(f"No loader registered for: {path}")
        raise ValueError(f"No loader registered for: {path}")

    def load(self, name, path):
        """Synchronous, blocking load. Fine for a loading screen or
        startup assets. Reuses a cached asset if this path was
        already loaded under any name."""

        with self._lock:
            cached = self._cache.get(path)

        if cached is not None:
            with self._lock:
                self._assets[name] = cached
            return cached

        loader = self._find_loader(path)
        asset = loader.finalize(loader.load(path))

        with self._lock:
            self._assets[name] = asset
            self._cache[path] = asset

        return asset

    def queue(self, name, path):
        """Queue a load to happen in the background. If this path is
        already cached, or already loading under another name, this
        just piggybacks on that instead of loading it again."""

        with self._lock:

            if name in self._assets or name in self._pending:
                return

            cached = self._cache.get(path)
            if cached is not None:
                self._assets[name] = cached
                return

            self._pending.add(name)

            if path in self._path_pending:
                self._path_pending[path].append(name)
                return

            self._path_pending[path] = [name]

        loader = self._find_loader(path)
        self._in_queue.put((path, loader))

    def _run(self):

        while True:

            path, loader = self._in_queue.get()

            try:
                raw = loader.load(path)
                self._out_queue.put((path, loader, raw, None, None))
            except Exception as error:
                self._out_queue.put((path, loader, None, error,
                                     traceback.format_exc()))

    def update(self):
        """Call once per frame from the main thread. Finalizes
        anything the worker thread has finished loading, and hands
        the result to every name that was waiting on that path."""

        while not self._out_queue.empty():

            path, loader, raw, error, tb = self._out_queue.get()

            with self._lock:
                names = self._path_pending.pop(path, [])
                for name in names:
                    self._pending.discard(name)

            if error is not None:
                self._logger.error(f"Failed to load {path}: {error}\n{tb}")
                continue

            try:
                asset = loader.finalize(raw)
            except Exception as error:
                self._logger.error(
                    f"Failed to finalize {path}: {error}\n"
                    f"{traceback.format_exc()}"
                )
                continue

            with self._lock:
                self._cache[path] = asset
                for name in names:
                    self._assets[name] = asset

    def get(self, name):
        return self._assets.get(name)

    def ready(self, name):
        return name in self._assets

    def loading(self, name):
        return name in self._pending

    def cached(self, path):
        return path in self._cache
