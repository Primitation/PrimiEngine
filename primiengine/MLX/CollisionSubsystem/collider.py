import itertools

from .. import Log
from .. import Vector2


def rect_collide_rect(rect1, rect2):
    """Check if two rects (x, y, w, h) overlap."""
    return not (rect1[0] + rect1[2] <= rect2[0] or
                rect2[0] + rect2[2] <= rect1[0] or
                rect1[1] + rect1[3] <= rect2[1] or
                rect2[1] + rect2[3] <= rect1[1])


def rect_overlap_amount(rect1, rect2):
    """Return (overlap_x, overlap_y) between two rects."""
    overlap_x = min(rect1[0] + rect1[2], rect2[0] + rect2[2]) - max(rect1[0], rect2[0])
    overlap_y = min(rect1[1] + rect1[3], rect2[1] + rect2[3]) - max(rect1[1], rect2[1])
    return overlap_x, overlap_y


def rect_center(rect):
    """Return center (x, y) of a rect."""
    return (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2)


class Signal:
    """Minimal multicast delegate — the same idea as Unreal's
    dynamic multicast delegates (OnComponentBeginOverlap, etc).
    Bind any number of callables, broadcast() calls them all. A
    handler that raises is logged and skipped, it won't stop the
    other handlers from running."""

    def __init__(self):

        self._listeners = []
        self._logger = Log.get("collision")

    def bind(self, callback):

        self._listeners.append(callback)

    def unbind(self, callback):

        if callback in self._listeners:
            self._listeners.remove(callback)

    def broadcast(self, *args, **kwargs):

        for callback in list(self._listeners):

            try:
                callback(*args, **kwargs)
            except Exception:
                self._logger.exception(
                    f"Collision event handler {callback!r} raised"
                )


class Collider:
    """A collidable region tied to an owner. get_rect is a callable
    returning the current rect as (x, y, width, height) — pass e.g.
    a lambda that returns a tuple, so the collider always reflects
    the sprite's live position/size with no manual syncing.

    blocking: if True on BOTH colliders in a pair, overlap gets
    physically resolved each frame (pushed apart + bounced) instead
    of just firing overlap events. Needs owner.position (and
    owner.velocity, for bounce) to exist — a plain Vector2
    attribute, same as Player already has.

    bounce: restitution, 0..1. 0 = velocity into the surface is
    absorbed (stops dead on that axis), 1 = fully elastic bounce.

    static: this collider never moves when resolving a block, even
    if it has a position (e.g. walls, floors)."""

    def __init__(
        self,
        owner,
        get_rect,
        tag="default",
        collides_with=None,
        blocking=False,
        bounce=0.0,
        static=False,
        enabled=True
    ):

        self.owner = owner
        self.get_rect = get_rect
        self.tag = tag
        self.collides_with = collides_with  # None = collides with any tag
        self.blocking = blocking
        self.bounce = bounce
        self.static = static
        self.enabled = enabled

        self.on_begin_overlap = Signal()
        self.on_end_overlap = Signal()

    def rect(self):
        """Returns the rect as (x, y, width, height)."""
        rect = self.get_rect()
        # If it's already a tuple/list, return it
        if isinstance(rect, (tuple, list)):
            return rect
        # If it's some other object with x, y, width, height attributes
        return (rect.x, rect.y, rect.width, rect.height)

    def can_collide_with(self, other):

        if self.collides_with is None:
            return True

        return other.tag in self.collides_with


class SpatialGrid:
    """Uniform spatial hash used as a broad phase. Colliders are
    bucketed by the cell(s) their rect touches; only colliders
    sharing a cell are ever checked against each other in the
    narrow phase. This turns the naive O(n^2) all-pairs check into
    roughly O(n) for scenes where actors aren't all crammed on top
    of each other.

    cell_size should be in the same ballpark as your typical actor
    size — too small and actors span many cells (more insert work),
    too large and cells degrade back toward the whole world being
    one bucket (more candidate pairs)."""

    def __init__(self, cell_size=128):
        self.cell_size = cell_size
        self._cells = {}

    def clear(self):
        self._cells.clear()

    def _cell_range(self, rect):
        x, y, w, h = rect
        cs = self.cell_size
        cx0 = int(x // cs)
        cy0 = int(y // cs)
        cx1 = int((x + w) // cs)
        cy1 = int((y + h) // cs)
        return cx0, cy0, cx1, cy1

    def insert(self, collider, rect):
        cx0, cy0, cx1, cy1 = self._cell_range(rect)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                self._cells.setdefault((cx, cy), []).append(collider)

    def candidate_pairs(self):
        """Yields each unique pair of colliders that share at least
        one cell. A pair spanning multiple shared cells is only
        yielded once."""
        seen = set()
        for bucket in self._cells.values():
            n = len(bucket)
            if n < 2:
                continue
            for i in range(n):
                a = bucket[i]
                for j in range(i + 1, n):
                    b = bucket[j]
                    key = (a, b) if id(a) < id(b) else (b, a)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield key


class CollisionManager:

    def __init__(self, cell_size=128, max_correction_per_frame=64.0):

        self._colliders = []
        self._active_overlaps = set()  # set of (collider, collider) pairs

        self.width = None
        self.height = None

        self.max_correction_per_frame = max_correction_per_frame

        self._grid = SpatialGrid(cell_size)

        self._logger = Log.get("collision")
        self._warned_no_bounds = False

    def init(self, width, height):
        """Call once at startup so boundary resolution has a world
        size to clamp against. Without this, boundary resolution is
        skipped entirely (colliders simply won't be clamped to any
        edge)."""

        self.width = width
        self.height = height

    def register(
        self,
        owner,
        get_rect,
        tag="default",
        collides_with=None,
        blocking=False,
        bounce=0.0,
        static=False,
        enabled=True
    ) -> Collider:

        collider = Collider(
            owner,
            get_rect,
            tag,
            collides_with,
            blocking,
            bounce,
            static,
            enabled
        )

        self._colliders.append(collider)

        return collider

    def unregister(self, collider):

        if collider in self._colliders:
            self._colliders.remove(collider)

        self._active_overlaps = {
            pair for pair in self._active_overlaps
            if collider not in pair
        }

    def update(self):
        """Call once per frame."""

        active = [c for c in self._colliders if c.enabled]

        if len(active) < 1:
            return

        # Snapshot rects once up front (needed for the initial boundary
        # pass and to seed the spatial grid). If a collider's rect()
        # raises, log it once and drop it for this frame instead of
        # letting it blow up every pair it would have participated in.
        rects = {}
        for c in active:
            try:
                rects[c] = c.rect()
            except Exception:
                self._logger.exception(
                    f"rect() failed for {c.owner!r}, skipping this frame"
                )

        active = [c for c in active if c in rects]

        self._resolve_boundaries(active, rects)

        current_overlaps = set()

        if len(active) >= 2:
            # Refresh rects after boundary resolution may have moved things,
            # then build the broad-phase grid from the current positions.
            self._grid.clear()
            for c in active:
                rect = c.rect()
                rects[c] = rect
                self._grid.insert(c, rect)

            for a, b in self._grid.candidate_pairs():
                if not (a.enabled and b.enabled):
                    continue

                if not (a.can_collide_with(b) and b.can_collide_with(a)):
                    continue

                try:
                    # Live calls here (not the cached snapshot) so that
                    # resolving one pair earlier in this loop is reflected
                    # when checking later pairs in the same frame — same
                    # behavior as the original all-pairs version.
                    rect_a = a.rect()
                    rect_b = b.rect()
                    overlapping = rect_collide_rect(rect_a, rect_b)
                except Exception:
                    self._logger.exception(
                        f"Collision check failed between {a.owner!r} and {b.owner!r}"
                    )
                    continue

                if not overlapping:
                    continue

                pair = (a, b) if id(a) < id(b) else (b, a)
                current_overlaps.add(pair)

                if a.blocking and b.blocking:
                    self._resolve_block(a, b)

        # Resolve boundaries again after object-object collisions
        self._resolve_boundaries(active)

        began = current_overlaps - self._active_overlaps
        ended = self._active_overlaps - current_overlaps

        for a, b in began:
            a.on_begin_overlap.broadcast(a, b)
            b.on_begin_overlap.broadcast(b, a)

        for a, b in ended:
            a.on_end_overlap.broadcast(a, b)
            b.on_end_overlap.broadcast(b, a)

        self._active_overlaps = current_overlaps

    def _resolve_block(self, a, b):
        """Push a pair of blocking colliders apart along whichever
        axis (x or y) has the least overlap, then bounce each
        side's velocity off that axis. A collider only moves/bounces
        if it isn't static and its owner has a .position (and, for
        bounce, a .velocity) attribute."""

        try:
            rect_a = a.rect()
            rect_b = b.rect()
        except Exception:
            self._logger.exception(
                f"Collision resolve failed between "
                f"{a.owner!r} and {b.owner!r}"
            )
            return

        overlap_x, overlap_y = rect_overlap_amount(rect_a, rect_b)

        if overlap_x <= 0 or overlap_y <= 0:
            return

        center_a = rect_center(rect_a)
        center_b = rect_center(rect_b)

        dx = center_a[0] - center_b[0]
        dy = center_a[1] - center_b[1]

        if dx == 0 and dy == 0:
            # Perfectly coincident centers — e.g. two actors spawned on
            # the exact same position. There's no meaningful direction
            # to separate along, so break the tie deterministically
            # (based on identity, so it's stable frame to frame) rather
            # than always picking the same axis for every coincident pair.
            dx = 1.0 if (id(a) ^ id(b)) & 1 else -1.0

        # normal points AWAY from b, toward a — i.e. the direction `a`
        # needs to move to separate from `b`. Using > here (not <) is
        # the fix: the previous version pointed the normal toward the
        # other object instead of away from it, which pushed already-
        # overlapping actors deeper into each other instead of apart —
        # most visible when actors spawn stacked on the same position.
        if overlap_x < overlap_y:
            normal = Vector2(1, 0) if dx > 0 else Vector2(-1, 0)
            penetration = overlap_x
        else:
            normal = Vector2(0, 1) if dy > 0 else Vector2(0, -1)
            penetration = overlap_y

        if self.max_correction_per_frame is not None:
            # Cap how much overlap gets resolved in a single frame. A
            # large initial overlap (actors spawned on top of each
            # other) then bleeds off over a few frames instead of
            # snapping them apart in one violent jump.
            penetration = min(penetration, self.max_correction_per_frame)

        a_movable = not a.static and hasattr(a.owner, "position")
        b_movable = not b.static and hasattr(b.owner, "position")

        if a_movable and b_movable:
            a_share, b_share = 0.5, 0.5
        elif a_movable:
            a_share, b_share = 1.0, 0.0
        elif b_movable:
            a_share, b_share = 0.0, 1.0
        else:
            return

        if a_movable and self._should_resolve(a, normal):
            a.owner.position += normal * penetration * a_share
            self._bounce(a, normal)

        if b_movable and self._should_resolve(b, -normal):
            b.owner.position -= normal * penetration * b_share
            self._bounce(b, -normal)

    def _should_resolve(self, collider, normal):
        """
        Returns True only if the collider is moving into the surface.

        normal points away from the collider it hit.
        """

        velocity = getattr(collider.owner, "velocity", None)

        if velocity is None:
            return True

        # Moving away from the surface
        if velocity.dot(normal) >= 0:
            return False

        return True

    def _bounce(self, collider, normal):
        """Reflect the owner's velocity off `normal` (which points
        away from the other collider), scaled by this collider's
        bounce. Only the velocity component heading into the
        surface is affected."""

        velocity = getattr(collider.owner, "velocity", None)

        if velocity is None:
            return

        into_surface = velocity.dot(normal)

        if into_surface < 0:
            velocity -= (1 + collider.bounce) * into_surface * normal

    def _resolve_boundaries(self, colliders, rects=None):
        """Resolve colliders against screen boundaries.

        Skips: disabled colliders, static colliders (walls/floors
        should never get clamped/moved), and colliders whose owner
        has no .position. Does nothing at all if init(width, height)
        was never called — better than silently clamping everything
        to a 0x0 world.
        """

        if self.width is None or self.height is None:
            if not self._warned_no_bounds:
                self._logger.warning(
                    "CollisionManager.update() called before init(width, height) — "
                    "boundary resolution is disabled until init() is called."
                )
                self._warned_no_bounds = True
            return

        for collider in colliders:
            if not collider.enabled or collider.static:
                continue

            owner = collider.owner
            if not hasattr(owner, "position"):
                continue

            rect = rects[collider] if rects is not None and collider in rects else collider.rect()
            position = owner.position
            velocity = getattr(owner, "velocity", None)

            # X boundary
            if rect[0] < 0:
                position.x = 0
                if velocity is not None:
                    velocity.x = abs(velocity.x)
            elif rect[0] + rect[2] > self.width:
                position.x = self.width - rect[2]
                if velocity is not None:
                    velocity.x = -abs(velocity.x)

            # Y boundary
            if rect[1] < 0:
                position.y = 0
                if velocity is not None:
                    velocity.y = abs(velocity.y)
            elif rect[1] + rect[3] > self.height:
                position.y = self.height - rect[3]
                if velocity is not None:
                    velocity.y = -abs(velocity.y)
