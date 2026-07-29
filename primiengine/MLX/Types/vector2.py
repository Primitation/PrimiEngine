import math


class Vector2:

    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vector2({self.x}, {self.y})"

    def __eq__(self, other):
        return isinstance(other, Vector2) and self.x == other.x and self.y == other.y

    def __iter__(self):
        yield self.x
        yield self.y

    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)

    def __neg__(self):
        return Vector2(-self.x, -self.y)

    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return Vector2(self.x / scalar, self.y / scalar)

    def dot(self, other):
        return self.x * other.x + self.y * other.y

    def cross(self, other):
        """2D 'cross product' — a scalar, not a vector: the z
        component you'd get treating both as 3D vectors with z=0.
        Sign tells you which side `other` is on relative to self."""
        return self.x * other.y - self.y * other.x

    def length(self):
        return math.hypot(self.x, self.y)

    def length_squared(self):
        return self.x * self.x + self.y * self.y

    def normalize(self):
        length = self.length()
        if length == 0:
            return Vector2(0, 0)
        return Vector2(self.x / length, self.y / length)

    def to_tuple(self):
        return (self.x, self.y)

    @classmethod
    def zero(cls):
        return cls(0.0, 0.0)

    @classmethod
    def one(cls):
        return cls(1.0, 1.0)
