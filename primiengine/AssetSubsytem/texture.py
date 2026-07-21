import pygame
from pathlib import Path


class Texture:
    _cache = {}

    def __init__(self, path: str):
        self.path = Path(path)

        if str(self.path) in Texture._cache:
            self.surface = Texture._cache[str(self.path)]
        else:
            self.surface = pygame.image.load(
                self.path
            ).convert_alpha()

            Texture._cache[str(self.path)] = self.surface

    @property
    def size(self):
        return self.surface.get_size()

    def copy(self):
        return self.surface.copy()
