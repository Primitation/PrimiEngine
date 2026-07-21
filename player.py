import pygame
from primiengine import Actor, Render
from primiengine.Graphics.sprite import Sprite
from primiengine import Log
from primiengine.CollisionSubsystem.collisionsubsystem import Collision


class Player(Actor):

    def __init__(
        self,
        texture,
        position=(0, 0),
        speed=200,
        velocity=(1, 1)
    ):
        super().__init__()
        self.log_player = Log.get("Player")
        self.texture = texture

        self.position = pygame.Vector2(position)

        self.speed = speed

        self.velocity = pygame.Vector2(velocity)

        self.sprite = None
        self.collider = None

        self._create_sprite()
        self._create_collider()

    def _create_sprite(self):

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

    def _create_collider(self):

        self.collider = Collision.register(
            self,
            self.sprite.get_rect,
            tag="player",
            blocking=True,
            bounce=0.8
        )

        self.collider.on_begin_overlap.bind(self._on_begin_overlap)
        self.collider.on_end_overlap.bind(self._on_end_overlap)

    def _on_begin_overlap(self, this, other):

        self.logger.info(f"began overlapping {other.owner!r} ({other.tag})")

    def _on_end_overlap(self, this, other):

        self.logger.info(f"stopped overlapping {other.owner!r} ({other.tag})")

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
