# src/navigation/core/sensor_transform.py

from __future__ import annotations

import numpy as np


def phone_to_navigation_2d(
    linear_accel_x: float,
    linear_accel_y: float,
    heading_rad: float,
    forward_device: tuple[float, float] = (0.0, 1.0),
) -> np.ndarray:
    """
    Convert phone-frame horizontal linear acceleration to local ENU.

    Assumption:
        - Phone is mounted flat in the vehicle.
        - Navigation frame: +East = X, +North = Y.
        - ``heading_rad`` is the compass bearing clockwise from North:
            0       = North
            +pi/2   = East

    ``forward_device`` selects which device axis points forward. The default
    ``(0, 1)`` is device +Y (the phone top edge), matching the alignment
    presets in ``src/calibration/phone_alignment.py``.

    Returns ``[east, north]`` acceleration.
    """

    forward_x, forward_y = forward_device

    x = float(linear_accel_x)
    y = float(linear_accel_y)

    # Forward component along the selected device axis; lateral component to
    # its right-hand side (i.e. 90 deg clockwise from forward).
    forward = forward_x * x + forward_y * y
    lateral = -forward_y * x + forward_x * y

    c = np.cos(heading_rad)
    s = np.sin(heading_rad)

    # Forward = [sin(h), cos(h)]; right/lateral = [cos(h), -sin(h)].
    east = forward * s + lateral * c
    north = forward * c - lateral * s

    return np.array([east, north], dtype=float)