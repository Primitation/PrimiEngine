from .component import Component
from ... import Assets
from ... import Vector2


class SpriteComponent(Component):
    """A static, single-image sprite.

    Same lazy/caching behavior AActor.sprite used to have: this
    doesn't hold the loaded image itself, only the path. `.sprite`
    resolves from AssetSubsystem's cache on every access — it reads
    back None until the background load finishes, then the same
    (cached, shared) Texture every other user of that path gets.
    """

    def __init__(self, path: str = None, local_offset=(0.0, 0.0),
                 offset_rotates=True, center: bool = False,
                 enabled: bool = True, local_rotation=0.0):
        super().__init__(enabled)
        self._path = path
        self.local_position = local_offset
        self.offset_rotates = offset_rotates
        self.local_rotation = local_rotation
        self.center = center

    def on_added(self, actor):
        super().on_added(actor)
        if self._path is not None:
            Assets.queue(self._path)

    def set_sprite(self, path: str):
        """Swap to a different static image."""
        self._path = path
        Assets.queue(path)

    @property
    def sprite(self):
        if self._path is None:
            return None
        return Assets.get(self._path)

    @property
    def width(self):
        sprite = self.sprite
        return sprite.width if sprite is not None else 0

    @property
    def height(self):
        sprite = self.sprite
        return sprite.height if sprite is not None else 0

    def get_world_position(self):
        """Component.get_world_position() (actor position, plus any
        local_offset rotated-with-actor if offset_rotates=True), then
        — if center=True — an ADDITIONAL, deliberately UNROTATED
        shift by half this sprite's own scaled width/height.

        Why unrotated: draw_sprite already rotates the sprite's
        pixels around the center of its own box (pivot=(0.5,0.5)).
        Running the centering shift through the same rotate-with-
        actor math as local_offset would rotate it too — the box's
        top-left would trace a small circle around the actor's
        position every frame instead of sitting still under it,
        which looks like the sprite drifting/swinging as it turns.
        Centering is pure geometry (align the box under wherever the
        actor/offset already put it); the one actual visual rotation
        stays entirely draw_sprite's job."""

        x, y = super().get_world_position()

        if self.center and self.actor is not None:
            width = self.width * self.actor.scale.x
            height = self.height * self.actor.scale.y
            x -= width / 2
            y -= height / 2

        return (x, y)

    def get_rect(self):
        """Rect (x, y, width, height) from the actor's position and
        scale — handy to pass straight into a ColliderComponent as
        `get_rect=sprite_component.get_rect`, or to use as the
        fallback ColliderComponent picks up automatically when no
        get_rect is given."""
        actor = self.actor
        world_pos = self.get_world_position()
        width = self.width * actor.scale.x
        height = self.height * actor.scale.y
        return (world_pos[0], world_pos[1], width, height)
