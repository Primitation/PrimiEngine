class Animation:

    def __init__(
        self,
        frames,
        speed=100
    ):

        self.frames = frames
        self.speed = speed

        self.timer = 0
        self.index = 0

    def update(self, dt):

        self.timer += dt

        if self.timer >= self.speed:

            self.timer = 0
            self.index += 1

            if self.index >= len(self.frames):
                self.index = 0

    def frame(self):

        return self.frames[self.index]
