from .loader import AssetManager, TextureLoader, SoundLoader


class AssetSubsystem:

    def __init__(self):

        self._manager = AssetManager()

        self._manager.register(TextureLoader())
        self._manager.register(SoundLoader())

    def register(self, loader):

        self._manager.register(loader)

    def load(self, name: str, path: str):

        return self._manager.load(name, path)

    def queue(self, name: str, path: str):

        self._manager.queue(name, path)

    def update(self):

        self._manager.update()

    def get(self, name: str):

        return self._manager.get(name)

    def ready(self, name: str) -> bool:

        return self._manager.ready(name)

    def loading(self, name: str) -> bool:

        return self._manager.loading(name)

    def cached(self, path: str) -> bool:

        return self._manager.cached(path)


# Global asset system
Assets = AssetSubsystem()
