import pygame

from ..LogSubsystem.logsubsystem import Log


class Atlas:

    def __init__(
        self,
        texture,
        tile_size
    ):

        self.texture = texture
        self.tile_size = tile_size

        self._logger = Log.get("graphics")

    def get(
        self,
        x,
        y
    ):

        rect = pygame.Rect(
            x*self.tile_size,
            y*self.tile_size,
            self.tile_size,
            self.tile_size
        )

        try:
            return self.texture.surface.subsurface(rect)
        except (ValueError, pygame.error):
            self._logger.error(
                f"Atlas tile ({x}, {y}) at tile_size={self.tile_size} "
                f"is out of bounds for this texture"
            )
            raise
