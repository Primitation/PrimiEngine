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

        image = pygame.transform.scale(
            image,
            (
                int(image.width*self.scale.x),
                int(image.height*self.scale.y)
            )
        )

        if self.rotation:
            image = pygame.transform.rotate(
                image,
                self.rotation
            )

        return image

    def draw(self, surface):

        if not self.visible:
            return

        image = self.transform()

        rect = image.get_rect(
            center=self.position
        )

        surface.blit(image, rect)
