from .collider import CollisionManager, Collider
from .. import log_timing, Log

class CollisionSubsystem:

    def __init__(self, cell_size=128, max_correction_per_frame=64.0):

        self._manager = CollisionManager(cell_size, max_correction_per_frame)
        self._logger = Log.get("collision")

    def init(self, width: int, height: int):
        """Call once at startup (e.g. right alongside Renderer.init())
        so boundary resolution knows the world size to clamp against.
        Without this, boundary resolution is skipped rather than
        crashing or clamping to a 0x0 world."""

        self._manager.init(width, height)

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
        a block (e.g. walls/floors), and is never clamped to the
        world boundary either."""

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
    
    @log_timing()
    def update(self):
        """Call once per frame. Fires on_begin_overlap /
        on_end_overlap on affected colliders."""

        self._manager.update()


# Global collision system
Collision = CollisionSubsystem()
