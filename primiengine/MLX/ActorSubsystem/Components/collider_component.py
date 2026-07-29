from .component import Component
from Engine import Collision


class ColliderComponent(Component):
    """Thin component wrapper around CollisionSubsystem's Collider.

    Registers itself in on_added() — once self.actor exists, so
    get_rect can default to reading a sibling sprite component — and
    unregisters in destroy(), so you never have to remember to call
    Collision.unregister() yourself when an actor is removed;
    AActor.destroy() does it for you via component.destroy().

    get_rect: optional callable returning (x, y, width, height). If
    omitted, this component looks for another component on the same
    actor that exposes get_rect() (SpriteComponent /
    AnimatedSpriteComponent both do) and uses that; failing that, it
    falls back to a 1x1 box at the actor's position scaled by
    actor.scale. Pass your own get_rect when the hitbox shouldn't
    just track the visible sprite 1:1 (e.g. a hitbox that ignores a
    punch/squash animation on the sprite's scale — see Actor.get_rect
    for that exact case).

    blocking / bounce / static / tag / collides_with: same meaning as
    CollisionSubsystem.register() — see that docstring.
    """

    def __init__(
        self,
        get_rect=None,
        tag="default",
        collides_with=None,
        blocking=False,
        bounce=0.0,
        static=False,
        enabled=True,
    ):
        self._collider = None

        super().__init__(enabled)

        self._get_rect_override = get_rect
        self.tag = tag
        self.collides_with = collides_with
        self.blocking = blocking
        self.bounce = bounce
        self.static = static

    def on_added(self, actor):
        super().on_added(actor)

        self._collider = Collision.register(
            owner=actor,
            get_rect=self._get_rect_override or self._default_get_rect,
            tag=self.tag,
            collides_with=self.collides_with,
            blocking=self.blocking,
            bounce=self.bounce,
            static=self.static,
            enabled=self.enabled,
        )

    def _default_get_rect(self):
        for component in self.actor.components:
            if component is self:
                continue
            get_rect = getattr(component, "get_rect", None)
            if get_rect is not None:
                return get_rect()

        actor = self.actor
        return (actor.position.x, actor.position.y, actor.scale.x, actor.scale.y)

    @property
    def collider(self):
        """The underlying Collider, if you need direct access."""
        return self._collider

    @property
    def on_begin_overlap(self):
        return self._collider.on_begin_overlap

    @property
    def on_end_overlap(self):
        return self._collider.on_end_overlap

    def rect(self):
        return self._collider.rect()

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value
        if self._collider is not None:
            self._collider.enabled = value

    def destroy(self):
        if self._collider is not None:
            Collision.unregister(self._collider)
            self._collider = None
        super().destroy()
