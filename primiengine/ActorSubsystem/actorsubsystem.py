import threading
import pygame
from typing import TypeVar, Type


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
        Actors.add(self)

    def update(self, dt):
        pass


T = TypeVar("T", bound=Actor)


class ActorSubsystem:

    def __init__(self):

        self._actors = []
        self._lock = threading.Lock()

        self._clock = pygame.time.Clock()
        self._fps = 60

        self._running = False
        self._thread = None

        self.tick = Event()

    def init(self, fps: int = 60):
        """Call once, at startup, to start the actor update thread."""

        self._fps = fps

        self._running = True

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def add(self, actor: Actor):
        """Thread-safe: call this from wherever your game logic
        lives, it doesn't have to be the actor thread. Subscribes
        the actor's update() to the tick event."""

        with self._lock:
            self._actors.append(actor)

        self.tick.subscribe(actor.update)

    def remove(self, actor: Actor):

        with self._lock:
            if actor in self._actors:
                self._actors.remove(actor)

        self.tick.unsubscribe(actor.update)

    def _run(self):

        while self._running:

            dt = self._clock.tick(self._fps)

            self.tick.emit(dt)

            with self._lock:
                dead = [a for a in self._actors if not a.alive]

            for actor in dead:
                self.remove(actor)

    def close(self):

        self._running = False

        if self._thread:
            self._thread.join()

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
