class Color:
    """r, g, b, a as ints 0-255. Ties directly into how mlx wants
    pixel data: mlx_pixel_put() and the raw buffer from
    mlx_get_data_addr() both use 0xAARRGGBB packed into a 4-byte
    little-endian value (see the checkerboard placeholder in
    TextureLoader, and mlx's own mlxtest.py) — .to_argb() and
    .to_bytes() give you that directly."""

    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r=0, g=0, b=0, a=255):
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    def __repr__(self):
        return f"Color({self.r}, {self.g}, {self.b}, {self.a})"

    def __eq__(self, other):
        return (
            isinstance(other, Color)
            and self.r == other.r
            and self.g == other.g
            and self.b == other.b
            and self.a == other.a
        )

    def to_argb(self) -> int:
        """Packs to the 0xAARRGGBB int mlx_pixel_put() expects."""
        return (self.a << 24) | (self.r << 16) | (self.g << 8) | self.b

    def to_bytes(self) -> bytes:
        """4 little-endian bytes — write this directly into a slice
        of the memoryview mlx_get_data_addr() returns."""
        return self.to_argb().to_bytes(4, "little")

    @classmethod
    def from_argb(cls, value: int):
        return cls(
            r=(value >> 16) & 0xFF,
            g=(value >> 8) & 0xFF,
            b=value & 0xFF,
            a=(value >> 24) & 0xFF,
        )

    def to_floats(self):
        """r, g, b, a as 0.0-1.0 floats."""
        return (self.r / 255, self.g / 255, self.b / 255, self.a / 255)

    @classmethod
    def white(cls):
        return cls(255, 255, 255, 255)

    @classmethod
    def black(cls):
        return cls(0, 0, 0, 255)

    @classmethod
    def transparent(cls):
        return cls(0, 0, 0, 0)

    @classmethod
    def magenta(cls):
        return cls(255, 0, 255, 255)
