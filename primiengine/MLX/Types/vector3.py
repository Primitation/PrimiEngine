import math


class Vector3:

    __slots__ = ("x", "y", "z")

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"Vector3({self.x}, {self.y}, {self.z})"

    def __eq__(self, other):
        return (
            isinstance(other, Vector3)
            and self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return Vector3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def length_squared(self):
        return self.x * self.x + self.y * self.y + self.z * self.z

    def normalize(self):
        length = self.length()
        if length == 0:
            return Vector3(0, 0, 0)
        return Vector3(self.x / length, self.y / length, self.z / length)

    def to_tuple(self):
        return (self.x, self.y, self.z)

    @classmethod
    def zero(cls):
        return cls(0.0, 0.0, 0.0)

    @classmethod
    def one(cls):
        return cls(1.0, 1.0, 1.0)
