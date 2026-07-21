class Renderer:

    def __init__(self, screen):

        self.screen = screen
        self.layers = {}

    def add(
        self,
        sprite,
        layer=0
    ):

        if layer not in self.layers:
            self.layers[layer] = []

        self.layers[layer].append(sprite)

    def render(self):

        for layer in sorted(self.layers):

            for sprite in self.layers[layer]:

                sprite.draw(
                    self.screen
                )
