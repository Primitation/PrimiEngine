class WorldClass:
    """Contains actors belonging to the current scene.

    ActorSubsystem handles lifetime/ticking.
    World handles scene visibility/rendering.
    """

    def __init__(self):
        self._actors = []

    def add(self, actor):
        if actor not in self._actors:
            self._actors.append(actor)

    def remove(self, actor):
        if actor in self._actors:
            self._actors.remove(actor)

    def clear(self):
        self._actors.clear()

    def find(self, actor_class):
        """
        Find the first actor matching the given class.

        Example:
            player = World.find(Player)
        """
        for actor in self._actors:
            if isinstance(actor, actor_class):
                return actor

        return None

    def find_all(self, actor_class):
        """
        Find all actors matching the given class.

        Example:
            ghosts = World.find_all(Ghost)
        """
        return [
            actor for actor in self._actors
            if isinstance(actor, actor_class)
        ]

    def __iter__(self):
        return iter(self._actors)

    def __len__(self):
        return len(self._actors)


World = WorldClass()
