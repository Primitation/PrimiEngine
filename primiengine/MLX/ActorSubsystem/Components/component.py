from abc import ABC
import math


class Component(ABC):
    """Base class for everything an Actor can carry as a component —
    SpriteComponent, AnimatedSpriteComponent, ColliderComponent, and
    later gameplay components like a Health component.

    An actor owns an ordered list of components (see
    AActor.add_component()). Every frame, AActor._tick() calls
    update() on each enabled/alive component before calling the
    actor's own update() — so components can, e.g., advance an
    animation before the actor reacts to it.

    Subclasses typically override on_added() (setup that needs
    self.actor to exist, e.g. registering with Collision),
    update(dt), and destroy() (release anything external, e.g.
    unregister from Collision). Always call super().destroy() so
    `alive` flips to False.
    """

    def __init__(self, enabled: bool = True):
        self.actor = None
        self.enabled = enabled
        self.alive = True
        self.local_position = (0.0, 0.0)  # Offset from actor's position
        self.local_rotation = 0.0  # Offset from actor's rotation
        self.offset_rotates = True  # If True, offset rotates with actor

    def on_added(self, actor):
        """Called once by AActor.add_component(), right after this
        component has been appended to actor.components. self.actor
        is set here — do any setup that needs the owning actor to
        already exist (e.g. Collision.register(owner=actor, ...))."""
        self.actor = actor

    def update(self, dt):
        """Override for per-frame work. Only called while the
        component is enabled and alive, and its actor is alive."""
        pass

    def destroy(self):
        """Override to release anything external (unregister from
        Collision, cancel a pending asset load, etc). Always call
        super().destroy() so `alive` becomes False and the actor
        stops ticking/rendering it."""
        self.alive = False

    def get_world_position(self):
        """Get the world position of this component (actor position +
        local offset), with the offset rotated around the actor's
        origin by the actor's current rotation when offset_rotates
        is True.

        Rotation convention matches AActor.rotation / the renderer's
        sprite rotation (0 = +x/right, 90 = +y/down, clockwise on
        screen as the angle increases) — an offset of (20, 0) ("20
        units in front" when facing right) correctly becomes (0, 20)
        ("in front", now pointing down) once the actor rotates to
        rotation=90, same direction the sprite itself visually turns.

        local_position accepts a plain (x, y) tuple/list OR anything
        with .x/.y (e.g. Vector2) — duck-typed rather than assuming
        an unpackable tuple, since plugging a Vector2 in directly is
        an easy mistake in a codebase that uses Vector2 everywhere
        else."""
        if self.actor is None:
            return (0.0, 0.0)

        # Start with actor's position
        pos_x = self.actor.position.x
        pos_y = self.actor.position.y

        offset = self.local_position
        offset_x, offset_y = (
            (offset.x, offset.y) if hasattr(offset, "x") else (offset[0], offset[1])
        )

        # Add local offset if not zero
        if offset_x != 0.0 or offset_y != 0.0:

            # If offset should rotate with the actor
            if self.offset_rotates:
                rotation = getattr(self.actor, "rotation", 0.0) + self.local_rotation
                # Convert to radians
                angle = math.radians(rotation)
                cos_a = math.cos(angle)
                sin_a = math.sin(angle)

                # Rotate the offset around origin (0,0)
                rotated_x = offset_x * cos_a - offset_y * sin_a
                rotated_y = offset_x * sin_a + offset_y * cos_a
                offset_x, offset_y = rotated_x, rotated_y

            pos_x += offset_x
            pos_y += offset_y

        return (pos_x, pos_y)
