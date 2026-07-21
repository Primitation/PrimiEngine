import threading
from typing import TypeVar, Type
from primiengine import Log


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


class Actor:
    """Base class for anything the ActorSubsystem manages. Override
    update()."""

    def __init__(self):

        self.alive = True

        self.logger = Log.get(self.__class__.__name__)

        Actors.add(self)

    def update(self, dt):
        pass


T = TypeVar("T", bound=Actor)


class ActorSubsystem:
    """Ticks every registered actor once per frame. Deliberately NOT
    thread-driven: actors touch pygame-derived state (sprite
    position, rects that Render/Collision read straight after),
    so ticking has to happen on the main thread, in step with
    everything else that reads that state."""

    def __init__(self):

        self._actors = []
        self._lock = threading.Lock()

        self.tick = Event()

    def init(self):
        """Call once, at startup. Kept for API symmetry with the
        other subsystems — there's no thread to spin up anymore."""
        pass

    def add(self, actor: Actor):
        """Registers the actor and subscribes its update() to the
        tick event. Thread-safe on the registration itself, even
        though ticking happens on the main thread."""

        with self._lock:
            self._actors.append(actor)

        self.tick.subscribe(actor.update)

    def remove(self, actor: Actor):

        with self._lock:
            if actor in self._actors:
                self._actors.remove(actor)

        self.tick.unsubscribe(actor.update)

    def update(self, dt):
        """Call once per frame from the main loop, passing the same
        dt (in ms) you got from clock.tick(). Ticks every actor,
        then cleans up anything that marked itself not alive during
        this tick."""

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

        return actor_class(
            *args,
            **kwargs
        )


# Global actor system
Actors = ActorSubsystem()
