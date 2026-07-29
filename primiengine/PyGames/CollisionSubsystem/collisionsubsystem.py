from .collider import CollisionManager, Collider


class CollisionSubsystem:

    def __init__(self):

        self._manager = CollisionManager()

    def register(
        self,
        owner,
        get_rect,
        tag: str = "default",
        collides_with=None,
        blocking: bool = False,
        bounce: float = 0.0,
        static: bool = False,
        enabled: bool = True
    ) -> Collider:
        """Register a collider. get_rect is a callable returning the
        current pygame.Rect (e.g. sprite.get_rect). tag identifies
        this collider's type; collides_with is an optional list of
        tags it's allowed to overlap with (None = collides with
        everything).

        blocking: if True on both sides of a pair, overlaps get
        physically resolved (pushed apart + bounced) each frame
        instead of just firing overlap events. Requires the owner
        to have a .position (pygame.Vector2), and a .velocity for
        bounce to do anything.

        bounce: restitution, 0..1 (0 = absorbs on impact, 1 = fully
        elastic). static: this collider never moves when resolving
        a block (e.g. walls/floors)."""

        return self._manager.register(
            owner,
            get_rect,
            tag,
            collides_with,
            blocking,
            bounce,
            static,
            enabled
        )

    def unregister(self, collider: Collider):

        self._manager.unregister(collider)

    def update(self):
        """Call once per frame. Fires on_begin_overlap /
        on_end_overlap on affected colliders."""

        self._manager.update()


# Global collision system
Collision = CollisionSubsystem()
