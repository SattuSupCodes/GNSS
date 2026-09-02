import math
import numpy as np

TAU = 2.0 * math.pi

def wrap_angle(angle: float) -> float:
    return (angle + math.pi) % TAU - math.pi

def heading_from_velocity(east: float, north: float) -> float:
    # Heading measured clockwise from North.
    return math.atan2(east, north)

def rotation_2d(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]], dtype=float)

class LocalENU:
    """Small local tangent-plane approximation around a GNSS origin."""
    def __init__(self, lat0: float, lon0: float):
        self.lat0 = float(lat0)
        self.lon0 = float(lon0)
        self._r = 6378137.0

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        lat0 = math.radians(self.lat0)
        east = math.radians(lon - self.lon0) * self._r * math.cos(lat0)
        north = math.radians(lat - self.lat0) * self._r
        return east, north

    def to_ll(self, east: float, north: float) -> tuple[float, float]:
        lat = self.lat0 + math.degrees(north / self._r)
        lon = self.lon0 + math.degrees(east / (self._r * math.cos(math.radians(self.lat0))))
        return lat, lon
