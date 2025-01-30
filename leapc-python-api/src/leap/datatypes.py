"""Wrappers for LeapC Data types"""

from .cstruct import LeapCStruct
from .enums import HandType
from leapc_cffi import ffi
from math import sqrt

print("DEBUG: This is the actual leap.datatypes being imported:", __file__)


class FrameData:
    """Wrapper which owns all the data required to read the Frame

    A LEAP_TRACKING_EVENT has a fixed size, but some fields are pointers to memory stored
    outside of the struct. This means the size required for all the information about a
    frame is larger than the size of the struct.

    This wrapper owns the buffer required for all of that data. Reading attributes or
    items from this wrapper returns the corresponding item or wrapper on the underlying
    LEAP_TRACKING_EVENT.

    It is intended to by used in the TrackingEvent constructor.
    """

    def __init__(self, size):
        self._buffer = ffi.new("char[]", size)
        self._frame_ptr = ffi.cast("LEAP_TRACKING_EVENT*", self._buffer)

    def __getattr__(self, name):
        return getattr(self._frame_ptr, name)

    def __getitem__(self, key):
        return self._frame_ptr[key]

    def frame_ptr(self):
        return self._frame_ptr


class FrameHeader(LeapCStruct):
    @property
    def frame_id(self):
        return self._data.frame_id

    @property
    def timestamp(self):
        return self._data.timestamp


class Vector(LeapCStruct):
    def __init__(self, data=None):
        # If no data is given, allocate a brand new LEAP_VECTOR
        if data is None:
            data = ffi.new("LEAP_VECTOR*")  # a pointer to an empty LEAP_VECTOR
            data = data[0]                 # get the struct itself
        super().__init__(data)

    
    def __getitem__(self, idx):
        return self._data.v[idx]

    def __iter__(self):
        return [self._data.v[i] for i in range(3)].__iter__()
    
    def __sub__(self, other):
        """Subtracts two Vector objects and returns a new Vector."""
        if not isinstance(other, Vector):
            raise TypeError("Subtraction is only supported between two Vector objects")

        # Create a new Vector object with the difference of x, y, z components
        result = Vector()
        result._data.x = self._data.x - other._data.x
        result._data.y = self._data.y - other._data.y
        result._data.z = self._data.z - other._data.z

        return result
    
    def magnitude(self):
        return float(sqrt(self._data.x ** 2 + self._data.y ** 2 + self._data.z ** 2))

    @property
    def x(self):
        return self._data.x

    @property
    def y(self):
        return self._data.y

    @property
    def z(self):
        return self._data.z


class Quaternion(LeapCStruct):
    def __getitem__(self, idx):
        return self._data.v[idx]

    def __iter__(self):
        return [self._data.v[i] for i in range(4)].__iter__()

    @property
    def x(self):
        return self._data.x

    @property
    def y(self):
        return self._data.y

    @property
    def z(self):
        return self._data.z

    @property
    def w(self):
        return self._data.w


class Palm(LeapCStruct):
    @property
    def position(self):
        return Vector(self._data.position)

    @property
    def stabilized_position(self):
        return Vector(self._data.stabilized_position)

    @property
    def velocity(self):
        return Vector(self._data.velocity)

    @property
    def normal(self):
        return Vector(self._data.normal)

    @property
    def width(self):
        return self._data.width

    @property
    def direction(self):
        return Vector(self._data.direction)

    @property
    def orientation(self):
        return Quaternion(self._data.orientation)


class Bone(LeapCStruct):
    @property
    def prev_joint(self):
        return Vector(self._data.prev_joint)

    @property
    def next_joint(self):
        return Vector(self._data.next_joint)

    @property
    def width(self):
        return self._data.width

    @property
    def rotation(self):
        return Quaternion(self._data.rotation)


class Digit(LeapCStruct):
    @property
    def finger_id(self):
        return self._data.finger_id

    @property
    def bones(self):
        return [self.metacarpal, self.proximal, self.intermediate, self.distal]

    @property
    def metacarpal(self):
        return Bone(self._data.metacarpal)

    @property
    def proximal(self):
        return Bone(self._data.proximal)

    @property
    def intermediate(self):
        return Bone(self._data.intermediate)

    @property
    def distal(self):
        return Bone(self._data.distal)
    
    @property
    def length(self):
        # Use self.distal.next_joint, not self._data.distal.next_joint
        distal_next = self.distal.next_joint       # => a Vector
        metacarpal_prev = self.metacarpal.prev_joint  # => another Vector
        return (distal_next - metacarpal_prev).magnitude()

    @property
    def is_extended(self):
        return self._data.is_extended
    
    
    

class Hand(LeapCStruct):
    @property
    def id(self):
        return self._data.id

    @property
    def flags(self):
        return self._data.flags

    @property
    def type(self):
        return HandType(self._data.type)

    @property
    def confidence(self):
        return self._data.confidence

    @property
    def visible_time(self):
        return self._data.visible_time

    @property
    def pinch_distance(self):
        return self._data.pinch_distance

    @property
    def grab_angle(self):
        return self._data.grab_angle

    @property
    def pinch_strength(self):
        return self._data.pinch_strength

    @property
    def grab_strength(self):
        return self._data.grab_strength

    @property
    def palm(self):
        return Palm(self._data.palm)

    @property
    def thumb(self):
        return Digit(self._data.thumb)

    @property
    def index(self):
        return Digit(self._data.index)

    @property
    def middle(self):
        return Digit(self._data.middle)

    @property
    def ring(self):
        return Digit(self._data.ring)

    @property
    def pinky(self):
        return Digit(self._data.pinky)

    @property
    def digits(self):
        return [self.thumb, self.index, self.middle, self.ring, self.pinky]

    @property
    def arm(self):
        return Bone(self._data.arm)


class Image(LeapCStruct):
    @property
    def matrix_version(self):
        return self._data.matrix_version
