from .atlas import Atlas
from .animation import Animation
from .sprite import Sprite

from ..LogSubsystem.logsubsystem import Log


class GraphicsFactory:
    """Builds Atlas / Animation / Sprite objects on top of an asset
    provider (e.g. AssetSubsystem). Only requires the provider to
    have a .get(name) method — Graphics doesn't import or depend on
    AssetSubsystem itself, so the dependency only runs one way, at
    call time, and only through this class."""

    def __init__(self, assets):

        self._assets = assets
        self._atlases = {}  # (name, tile_size) -> Atlas

        self._logger = Log.get("graphics")

    def atlas(self, name: str, tile_size: int) -> Atlas:
        """Get (or lazily build) the Atlas for an already-loaded
        texture asset, sliced into tiles of tile_size. Atlases are
        cached per (name, tile_size), so repeated calls are free."""

        key = (name, tile_size)

        cached = self._atlases.get(key)
        if cached is not None:
            return cached

        texture = self._assets.get(name)
        if texture is None:
            message = (
                f"Cannot build atlas for '{name}': asset not loaded "
                f"yet (use load()/queue() first)"
            )
            self._logger.error(message)
            raise ValueError(message)

        atlas = Atlas(texture, tile_size)
        self._atlases[key] = atlas

        return atlas

    def animation(self, name: str, tile_size: int,
                  coords, speed=100) -> Animation:
        """Build an Animation by pulling frames out of the atlas for
        an already-loaded texture. coords is a sequence of (x, y)
        tile positions, in the order the animation should play."""

        atlas = self.atlas(name, tile_size)
        frames = [atlas.get(x, y) for x, y in coords]

        return Animation(frames, speed)

    def sprite(self, name: str, position=(0, 0)) -> Sprite:
        """Build a Sprite from an already-loaded texture asset.
        Returns a fresh Sprite each call (not cached), since sprites
        typically need independent position/rotation/scale even
        when they share the same texture."""

        texture = self._assets.get(name)
        if texture is None:
            message = (
                f"Cannot build sprite for '{name}': asset not loaded "
                f"yet (use load()/queue() first)"
            )
            self._logger.error(message)
            raise ValueError(message)

        return Sprite(texture, position)
