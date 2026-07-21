from .texture import Texture


class Resources:

    textures = {}

    @classmethod
    def load_texture(cls, name, path):
        cls.textures[name] = Texture(path)

    @classmethod
    def texture(cls, name):
        return cls.textures[name]
