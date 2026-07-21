import pygame
from primiengine import Actor, Render


class Player(Actor):

    def __init__(
        self,
        texture,
        position=(0, 0),
        speed=200
    ):
        super().__init__()

        self.texture = texture

        self.position = pygame.Vector2(position)

        self.speed = speed

        self.velocity = pygame.Vector2(1, 1)

        self.sprite = None

        self._create_sprite()

    def _create_sprite(self):

        from primiengine.sprite import Sprite

        self.sprite = Sprite(
            self.texture,
            position=self.position
        )

        self.sprite.scale = pygame.Vector2(
            0.25,
            0.25
        )

        Render.add(
            self.sprite,
            layer=1
        )

    def update(self, dt):

        delta = dt / 1000

        self.position += (
            self.velocity *
            self.speed *
            delta
        )

        # keep sprite synchronized
        self.sprite.position = self.position

        rect = self.sprite.get_rect()

        screen_width = 800
        screen_height = 600

        if rect.left <= 0 or rect.right >= screen_width:
            self.velocity.x *= -1

        if rect.top <= 0 or rect.bottom >= screen_height:
            self.velocity.y *= -1
