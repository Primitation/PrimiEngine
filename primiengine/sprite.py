import pygame


class Sprite:

    def __init__(
        self,
        texture,
        position=(0, 0)
    ):
        self.texture = texture
        self.position = pygame.Vector2(position)

        self.rotation = 0
        self.scale = pygame.Vector2(1, 1)

        self.visible = True

    def transform(self):
        image = self.texture.surface
        width, height = image.get_size()

        image = pygame.transform.scale(
            image,
            (
                int(width * self.scale.x),
                int(height * self.scale.y)
            )
        )

        if self.rotation:
            image = pygame.transform.rotate(
                image,
                self.rotation
            )

        return image

    def get_rect(self):
        """Return a pygame.Rect representing
        the sprite's current position and size."""
        # Get the transformed image for accurate rotated bounds
        image = self.transform()
        rect = image.get_rect(center=self.position)
        return rect

    def draw(self, surface):

        if not self.visible:
            return

        image = self.transform()

        rect = image.get_rect(
            center=self.position
        )

        surface.blit(image, rect)
