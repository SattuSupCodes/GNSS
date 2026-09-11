"""Phone-frame -> navigation-frame alignment.

Transforms sensor measurements expressed in the smartphone (device) frame into
a consistent navigation/world (ENU) frame.

Key rule from the project constraints: **there is no universal phone mounting
orientation** — the driver may hold/mount the phone any way. This module makes
the alignment convention explicit and configurable, keeps enough metadata to
identify exactly which transformation was applied, and never assumes the phone
is flat / forward-pointing.

Conventions
-----------
* Device frame: X = right, Y = up the long edge (screen top), Z = out of the
  screen (Android accelerometer convention).
* World frame: ENU (East, North, Up).
* The alignment is a unit quaternion ``q_align`` (or, equivalently, a 3x3
  rotation matrix) such that ``world = rotate(q_align, device)``.
  Applying the *conjugate* maps world -> device (inverse transform).
* Euler convention: ``R = Rz(yaw) * Ry(pitch) * Rx(roll)`` device -> world,
  matching :mod:`src.calibration.orientation_estimation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .orientation_estimation import (
    quat_conjugate,
    quat_from_euler,
    quat_multiply,
    quat_normalize,
    quat_rotate,
    quat_to_euler,
    quat_to_rotation_matrix,
)

DEVICE_FRAME = "device"
WORLD_FRAME = "ENU"


@dataclass
class AlignmentConvention:
    """An explicit description of how the phone is mounted, and the transform.

    ``yaw_deg/pitch_deg/roll_deg`` define the device->world rotation
    ``R = Rz(yaw)*Ry(pitch)*Rx(roll)``. ``description`` should say in words what
    ``yaw_deg == 0`` means (e.g. "device top edge points North, screen faces
    up") so real-world mounting intent survives in metadata.
    """

    name: str
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    description: str = ""
    source: str = "configured"

    def to_quaternion(self) -> np.ndarray:
        return quat_from_euler(
            np.deg2rad(float(self.yaw_deg)),
            np.deg2rad(float(self.pitch_deg)),
            np.deg2rad(float(self.roll_deg)),
        )

    def to_rotation_matrix(self) -> np.ndarray:
        return quat_to_rotation_matrix(self.to_quaternion())

    def inverse(self, name: Optional[str] = None) -> "AlignmentConvention":
        q = quat_conjugate(self.to_quaternion())
        y, p, r = quat_to_euler(q)
        return AlignmentConvention(
            name=name or (self.name + "_inv"),
            yaw_deg=float(np.degrees(y)),
            pitch_deg=float(np.degrees(p)),
            roll_deg=float(np.degrees(r)),
            description=f"Inverse of '{self.name}' (world -> device)",
            source=self.source,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "yaw_deg": self.yaw_deg,
            "pitch_deg": self.pitch_deg,
            "roll_deg": self.roll_deg,
            "description": self.description,
            "source": self.source,
        }


# Predefined presets. In every preset, screen faces up unless "UPRIGHT" appears.
# "TOP_<direction>" names the world direction the device's top edge (device +Y)
# points towards.
PRESET_CONVENTIONS: Dict[str, AlignmentConvention] = {
    "TOP_NORTH_SCREEN_UP": AlignmentConvention(
        name="TOP_NORTH_SCREEN_UP",
        yaw_deg=0.0,
        pitch_deg=0.0,
        roll_deg=0.0,
        description="Phone flat, screen up, top edge pointing North (device == ENU).",
    ),
    "TOP_EAST_SCREEN_UP": AlignmentConvention(
        name="TOP_EAST_SCREEN_UP",
        yaw_deg=-90.0,
        pitch_deg=0.0,
        roll_deg=0.0,
        description="Phone flat, screen up, top edge pointing East.",
    ),
    "TOP_SOUTH_SCREEN_UP": AlignmentConvention(
        name="TOP_SOUTH_SCREEN_UP",
        yaw_deg=180.0,
        pitch_deg=0.0,
        roll_deg=0.0,
        description="Phone flat, screen up, top edge pointing South.",
    ),
    "TOP_WEST_SCREEN_UP": AlignmentConvention(
        name="TOP_WEST_SCREEN_UP",
        yaw_deg=90.0,
        pitch_deg=0.0,
        roll_deg=0.0,
        description="Phone flat, screen up, top edge pointing West.",
    ),
    "TOP_UP_SCREEN_NORTH": AlignmentConvention(
        name="TOP_UP_SCREEN_NORTH",
        yaw_deg=180.0,
        pitch_deg=90.0,
        roll_deg=0.0,
        description=(
            "Phone upright (portrait), screen facing North/South plane, "
            "top edge pointing Up, back of phone pointing South."
        ),
    ),
}


def get_preset(name: str) -> AlignmentConvention:
    if name not in PRESET_CONVENTIONS:
        raise KeyError(
            f"Unknown alignment preset {name!r}. Available: "
            f"{sorted(PRESET_CONVENTIONS)}"
        )
    return PRESET_CONVENTIONS[name]


def alignment_metadata(
    convention: AlignmentConvention, applied_to: Optional[List[str]] = None
) -> Dict[str, object]:
    """Serialisable metadata describing an applied alignment transform."""
    return {
        "convention": convention.to_dict(),
        "device_frame": DEVICE_FRAME,
        "world_frame": WORLD_FRAME,
        "euler_order": "R = Rz(yaw) * Ry(pitch) * Rx(roll)",
        "transform_axis": "device -> world",
        "applied_to": list(applied_to) if applied_to else [],
    }


class PhoneAligner:
    """Applies a device->world alignment transform to sensor columns."""

    def __init__(self, convention: AlignmentConvention):
        self.convention = convention
        self.transform_quat = quat_normalize(convention.to_quaternion())
        self.transform_matrix = quat_to_rotation_matrix(self.transform_quat)

    @classmethod
    def from_preset(cls, name: str) -> "PhoneAligner":
        return cls(get_preset(name))

    @property
    def metadata(self) -> Dict[str, object]:
        return alignment_metadata(self.convention)

    # ------------------------------------------------------------------ #

    def align_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """Transform ``(n, 3)`` device-frame vectors into the world frame."""

        v = np.asarray(vectors, dtype=float)

        if v.ndim == 1:
            if v.size == 3:
                v = v.reshape(1, 3)
            else:
                v = v.reshape(-1, 3)

        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError(f"expected (n,3) vectors, got shape {v.shape}")

        out = np.full_like(v, np.nan, dtype=float)

        finite = np.isfinite(v).all(axis=1)

        if not np.any(finite):
            return out[0] if v.shape[0] == 1 else out

        out[finite] = np.array(
            [quat_rotate(self.transform_quat, row) for row in v[finite]],
            dtype=float,
        )

        return out[0] if v.shape[0] == 1 else out

    def align_single(self, vector: np.ndarray) -> np.ndarray:
        """Transform one device-frame 3-vector; returns a 3-vector."""
        v = np.asarray(vector, dtype=float).reshape(3)
        if not np.isfinite(v).all():
            return np.full(3, np.nan)
        return quat_rotate(self.transform_quat, v)

    def align_inverse(self, vectors: np.ndarray) -> np.ndarray:
        """Transform ``(n, 3)`` world-frame vectors back to the device frame."""
        v = np.asarray(vectors, dtype=float)
        if v.ndim == 1:
            if v.size == 3:
                v = v.reshape(1, 3)
            else:
                v = v.reshape(-1, 3)
        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError(f"expected (n,3) vectors, got shape {v.shape}")
        out = np.empty_like(v)
        finite = np.isfinite(v).all(axis=1)
        out[finite] = np.array(
            [quat_rotate(self.transform_quat, row, inverse=True) for row in v[finite]]
        )
        out[~finite] = np.nan
        return out[0] if v.shape[0] == 1 else out

    def align_dataframe(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        suffix: str = "_aligned",
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        """Add ``<col>_aligned`` world-frame columns for each requested sensor.

        ``columns`` defaults to accel/gyro/mag x/y/z canonical names. A copy is
        returned with raw device-frame columns untouched and aligned columns
        appended. Returns ``(frame, metadata)``.
        """
        if columns is None:
            columns = [
                "accel_x", "accel_y", "accel_z",
                "gyro_x", "gyro_y", "gyro_z",
                "mag_x", "mag_y", "mag_z",
            ]
        if len(columns) % 3 != 0:
            raise ValueError("columns must be provided as x/y/z triples")
        out = df.copy()
        for start in range(0, len(columns), 3):
            base = columns[start : start + 3]
            if not all(c in out.columns for c in base):
                continue
            raw = np.column_stack(
                [pd.to_numeric(out[c], errors="coerce").to_numpy() for c in base]
            )
            aligned = self.align_vectors(raw)
            for c, comp in zip(base, range(3)):
                out[c + suffix] = aligned[:, comp]
        return out, self.metadata


def validate_rotation_matrix(R: np.ndarray, tol: float = 1e-6) -> bool:
    """True when ``R`` is a valid rotation (orthonormal, det +1)."""
    R = np.asarray(R, dtype=float)
    if R.shape != (3, 3):
        return False
    err = float(np.max(np.abs(R @ R.T - np.eye(3))))
    return err < tol and abs(float(np.linalg.det(R)) - 1.0) < tol


def validate_quaternion(q: np.ndarray, tol: float = 1e-6) -> bool:
    """True when ``q`` is a unit quaternion (and thus a valid rotation)."""
    q = np.asarray(q, dtype=float)
    return q.shape == (4,) and abs(float(np.linalg.norm(q)) - 1.0) < tol


def compose_transforms(a: AlignmentConvention, b: AlignmentConvention) -> AlignmentConvention:
    """Compose two device->world conventions: returns a -> b (apply b's rotation
    on top of a's), also device->world composition when used chained."""
    q = quat_normalize(quat_multiply(b.to_quaternion(), a.to_quaternion()))
    y, p, r = quat_to_euler(q)
    return AlignmentConvention(
        name=f"{a.name} ⊗ {b.name}",
        yaw_deg=float(np.degrees(y)),
        pitch_deg=float(np.degrees(p)),
        roll_deg=float(np.degrees(r)),
        description=f"Composition of {a.name} followed by {b.name}",
    )