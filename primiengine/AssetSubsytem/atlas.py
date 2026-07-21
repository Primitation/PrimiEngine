import pygame


class Atlas:

    def __init__(
        self,
        texture,
        tile_size
    ):

        self.texture = texture
        self.tile_size = tile_size

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

        return self.texture.surface.subsurface(rect)
