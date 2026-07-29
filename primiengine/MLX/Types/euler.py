import math


class Euler:
    """Rotation as three axis angles, in radians. pitch = rotation
    around X, yaw = rotation around Y, roll = rotation around Z.
    Mainly a human-readable/editable form — for combining rotations
    or rotating vectors, convert to Quaternion first (Euler.to_quaternion()),
    since chained Euler angles are order-dependent and prone to
    gimbal lock."""

    __slots__ = ("pitch", "yaw", "roll")

    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch = pitch
        self.yaw = yaw
        self.roll = roll

    def __repr__(self):
        return f"Euler({self.pitch}, {self.yaw}, {self.roll})"

    def __eq__(self, other):
        return (
            isinstance(other, Euler)
            and self.pitch == other.pitch
            and self.yaw == other.yaw
            and self.roll == other.roll
        )

    @classmethod
    def from_degrees(cls, pitch, yaw, roll):
        return cls(math.radians(pitch), math.radians(yaw), math.radians(roll))

    def to_degrees(self):
        return (
            math.degrees(self.pitch),
            math.degrees(self.yaw),
            math.degrees(self.roll),
        )

    def to_quaternion(self):
        """Builds a Quaternion using pitch(X) -> yaw(Y) -> roll(Z)
        intrinsic rotation order. Import is local to avoid a circular
        import between euler.py and quaternion.py."""

        from .quaternion import Quaternion

        cp = math.cos(self.pitch * 0.5)
        sp = math.sin(self.pitch * 0.5)
        cy = math.cos(self.yaw * 0.5)
        sy = math.sin(self.yaw * 0.5)
        cr = math.cos(self.roll * 0.5)
        sr = math.sin(self.roll * 0.5)

        return Quaternion(
            w=cr * cp * cy + sr * sp * sy,
            x=cr * sp * cy - sr * cp * sy,
            y=cr * cp * sy + sr * sp * cy,
            z=sr * cp * cy - cr * sp * sy,
        )

    @classmethod
    def zero(cls):
        return cls(0.0, 0.0, 0.0)
