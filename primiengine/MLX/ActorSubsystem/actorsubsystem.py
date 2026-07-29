import threading
from functools import wraps
from typing import TypeVar, Type, Callable

from .. import Log
from .. import Vector2
from .. import World


class Event:
    """Simple pub/sub event — subscribe callables, emit() calls all
    of them with whatever arguments you pass. Not just for actors:
    any system can subscribe to Actors.tick."""

    def __init__(self):
        self._listeners = []

    def subscribe(self, callback):
        self._listeners.append(callback)

    def unsubscribe(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._listeners):
            callback(*args, **kwargs)


class AActor:
    """Base class for anything the ActorSubsystem manages.

    An actor is a position, a scale, and an ordered list of
    Components — nothing else lives on it directly anymore. Sprites
    and colliders used to be built into AActor itself; now they're
    just components (SpriteComponent / AnimatedSpriteComponent /
    ColliderComponent, see Engine.Components) that you attach with
    add_component(), same as any future gameplay component (Health,
    etc). Renderer/Collision/etc. read whatever components an actor
    happens to carry instead of assuming every actor has a sprite.

    Every frame, _tick() calls update(dt) on each enabled/alive
    component (in the order they were added), then calls this
    actor's own update(dt) — so a component like
    AnimatedSpriteComponent has already advanced before the actor's
    update() runs.

    Override update().
    """

    def __init__(
        self,
        position: Vector2 = None,
        scale: Vector2 = None,
        static=False,
    ):

        self.alive = True
        self.static = static

        self.position = (
            position
            if position is not None
            else Vector2.zero()
        )

        self.scale = (
            scale
            if scale is not None
            else Vector2(1, 1)
        )

        self.components = []

        self.logger = Log.get(self.__class__.__name__)

        Actors.add(self)

    def add_component(self, component):
        """Attach a component: appends it to self.components and
        fires its on_added(self) hook. Returns the component, so you
        can do e.g.
        `self.collider = self.add_component(ColliderComponent(...))`.
        """
        self.components.append(component)
        component.on_added(self)
        return component

    def remove_component(self, component):
        """Detach a component and destroy() it (unregistering it
        from whatever external system it hooked into, e.g.
        Collision)."""
        if component in self.components:
            self.components.remove(component)
        component.destroy()

    def get_component(self, component_type):
        """First attached component that is an instance of
        component_type, or None. E.g.
        actor.get_component(ColliderComponent)."""
        for component in self.components:
            if isinstance(component, component_type):
                return component
        return None

    def get_components(self, component_type):
        """Every attached component that is an instance of
        component_type."""
        return [
            component for component in self.components
            if isinstance(component, component_type)
        ]

    @property
    def rotation(self):
        """Rotation in degrees around the sprite's center."""
        return getattr(self, '_rotation', 0.0)

    @rotation.setter
    def rotation(self, value):
        self._rotation = float(value)

    # Also add a pivot point if you want off-center rotation
    @property
    def pivot(self):
        """Pivot point for rotation (as fraction of sprite size).
        Default: (0.5, 0.5) = center."""
        return getattr(self, '_pivot', (0.5, 0.5))

    @pivot.setter
    def pivot(self, value):
        self._pivot = value

    def _tick(self, dt):
        for component in list(self.components):
            if component.enabled and component.alive:
                component.update(dt)

        self.update(dt)

    def update(self, dt):
        pass

    def destroy(self):
        for component in list(self.components):
            component.destroy()
        self.components.clear()

        self.alive = False


T = TypeVar("T", bound=AActor)


class ActorSubsystem:
    """Ticks every registered actor once per frame. Deliberately NOT
    thread-driven: actors touch renderer-derived state (position,
    sprite) that Render/Collision read straight after, so ticking
    has to happen on the main thread, in step with everything else
    that reads that state."""

    def __init__(self):

        self._actors: list[AActor] = []
        self._lock = threading.Lock()

        self.tick = Event()
        self.paused = False

        self._logger = Log.get("actors")

    def init(self):
        """Call once, at startup. Kept for API symmetry with the
        other subsystems — there's no thread to spin up anymore."""
        pass

    def add(self, actor: AActor):
        """Registers the actor and subscribes its update() to the
        tick event. Thread-safe on the registration itself, even
        though ticking happens on the main thread."""

        with self._lock:
            self._actors.append(actor)

        self.tick.subscribe(actor._tick)

    def clear(self):
        with self._lock:
            for actor in self._actors:
                actor.destroy()

    def remove(self, actor: AActor):
        with self._lock:
            if actor in self._actors:
                self._actors.remove(actor)
                World.remove(actor)

        self.tick.unsubscribe(actor._tick)

    def pause(self):
        """Freeze every actor's update() until resume()/toggle_pause()."""
        self.paused = True
        self._logger.info("Actors paused")

    def resume(self):
        """Resume ticking actors after pause()."""
        self.paused = False
        self._logger.info("Actors resumed")

    def toggle_pause(self) -> bool:
        """Flip paused state and return the new value."""
        if self.paused:
            self.resume()
        else:
            self.pause()
        return self.paused

    def update(self, dt):
        """Call once per frame from the main loop, passing the same
        dt (in ms) you got from your clock. Ticks every actor unless
        paused, then cleans up anything that marked itself not alive
        during this tick — cleanup still runs while paused so nothing
        piles up waiting for a resume()."""

        if not self.paused:
            self.tick.emit(dt)

        with self._lock:
            dead = [actor for actor in self._actors if not actor.alive]

        for actor in dead:
            self.remove(actor)

    def close(self):
        """Kept for API symmetry — nothing to shut down anymore."""
        pass

    def spawn(
        self,
        actor_class: Type[T],
        *args,
        **kwargs
    ) -> T:

        random_spawn = kwargs.pop("random_spawn", False)

        actor = actor_class(
            *args,
            **kwargs
        )

        if random_spawn and hasattr(actor, "get_rect"):

            x, y, width, height = actor.get_rect()

            existing = [
                a.get_rect()
                for a in self._actors
                if hasattr(a, "get_rect") and a is not actor
            ]

            spawn_x, spawn_y = self.find_spawn_position(
                width,
                height,
                existing
            )

            actor.position.x = spawn_x
            actor.position.y = spawn_y

        World.add(actor)

        return actor

    def find_spawn_position(self, width, height, existing, max_attempts=30):
        import random
        from Engine import Renderer
        """Rejection-sample a position that doesn't overlap any
        already-spawned rect, so actors don't start on top of each
        other. Falls back to the last sampled position (still
        possibly overlapping) if it can't find a free spot in time —
        better than spinning forever once the screen gets crowded."""

        for _ in range(max_attempts):
            x = random.uniform(0, Renderer.width - width)
            y = random.uniform(0, Renderer.height - height)
            candidate = (x, y, width, height)

            if not any(self.rects_overlap(candidate, r) for r in existing):
                return x, y

        return x, y

    def rects_overlap(self, r1, r2):
        return not (
            r1[0] + r1[2] <= r2[0] or
            r2[0] + r2[2] <= r1[0] or
            r1[1] + r1[3] <= r2[1] or
            r2[1] + r2[3] <= r1[1]
        )


def on_end_of_anim(callback: Callable) -> Callable:
    """
    Decorator for a method whose first argument (after self) is an
    AnimatedSpriteComponent. Automatically chains `callback` onto the
    on_complete of the next set_animation() call the decorated
    method makes on that component — without disturbing any
    on_complete the method itself passed in.

    Usage: @on_end_of_anim(MyActor.some_handler)
           def play_death(self, anim: AnimatedSpriteComponent):
               anim.set_animation("death.png", 32, 32, ...)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, component, *args, **kwargs):

            logger = Log.get(self.__class__.__name__)

            original_set_animation = component.set_animation

            if hasattr(callback, "__self__"):
                cb = callback
            else:
                cb = lambda: callback(self)

            def intercepted_set_animation(*args, **kwargs):

                logger.debug(
                    f"Intercepted set_animation for {self.__class__.__name__}"
                )

                existing = kwargs.get("on_complete")

                def chained_callback():
                    logger.info(
                        f"Animation complete callback fired on "
                        f"{self.__class__.__name__}"
                    )

                    if existing:
                        logger.debug("Calling existing animation callback")
                        existing()

                    logger.debug("Calling decorator callback")
                    cb()

                kwargs["on_complete"] = chained_callback

                logger.debug(
                    "Injected on_complete callback into animation"
                )

                return original_set_animation(*args, **kwargs)

            component.set_animation = intercepted_set_animation

            try:
                return func(self, component, *args, **kwargs)

            finally:
                component.set_animation = original_set_animation
                logger.debug(
                    "Restored original set_animation"
                )

        return wrapper

    return decorator


# Global actor system
Actors = ActorSubsystem()
