from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.calibration.orientation_estimation import quat_rotate
from src.calibration.phone_alignment import PhoneAligner


LINEAR_ACCEL_COLUMNS = (
    "linear_accel_x",
    "linear_accel_y",
    "linear_accel_z",
)

ALIGNED_LINEAR_ACCEL_COLUMNS = (
    "linear_accel_x_aligned",
    "linear_accel_y_aligned",
    "linear_accel_z_aligned",
)

ORIENTATION_QUATERNION_COLUMNS = (
    "orient_qw",
    "orient_qx",
    "orient_qy",
    "orient_qz",
)


class NavigationSensorAdapter:
    """
    Convert calibrated smartphone sensor measurements into navigation-frame
    quantities consumed by the navigation backend.

    Preferred path
    --------------
    If a per-sample orientation quaternion is available, it is used to rotate
    the phone-frame linear acceleration into world ENU.

    Fallback path
    -------------
    A fixed PhoneAligner may be used when no orientation quaternion is
    available. This is mainly useful for simple/unit-test cases and should not
    be treated as the full vehicle-navigation solution.
    """

    def __init__(self, aligner: Optional[PhoneAligner] = None):
        self.aligner = aligner

    # ------------------------------------------------------------------ #
    # DataFrame transformation                                            #
    # ------------------------------------------------------------------ #

    def transform_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add ENU linear acceleration columns.

        If orientation quaternions are present, each acceleration vector is
        rotated using the corresponding device->world quaternion.
        Otherwise, the configured fixed PhoneAligner is used.
        """
        missing = [
            c for c in LINEAR_ACCEL_COLUMNS
            if c not in df.columns
        ]
        if missing:
            raise KeyError(
                f"missing required linear acceleration columns: {missing}"
            )

        out = df.copy()

        if all(c in out.columns for c in ORIENTATION_QUATERNION_COLUMNS):
            aligned = self._transform_with_orientation(out)
        else:
            if self.aligner is None:
                raise KeyError(
                    "orientation quaternion columns are unavailable and no "
                    "fallback PhoneAligner was provided"
                )

            vectors = np.column_stack(
                [
                    pd.to_numeric(out[c], errors="coerce").to_numpy(
                        dtype=float
                    )
                    for c in LINEAR_ACCEL_COLUMNS
                ]
            )

            aligned = np.asarray(
                self.aligner.align_vectors(vectors),
                dtype=float,
            )
            if aligned.ndim ==1:
                aligned = aligned.reshape(1,3)

        if aligned.shape != (len(out), 3):
            raise ValueError(
                "transformed acceleration has unexpected shape: "
                f"{aligned.shape}, expected {(len(out), 3)}"
            )

        for axis, idx in zip("xyz", range(3)):
            out[f"linear_accel_{axis}_aligned"] = aligned[:, idx]

        return out

    # ------------------------------------------------------------------ #
    # Single-sample transformation                                         #
    # ------------------------------------------------------------------ #

    def acceleration_enu(self, row: pd.Series) -> Optional[np.ndarray]:
        """
        Return [east, north] linear acceleration in m/s^2.

        Preferred source is the row's device->world orientation quaternion.
        """
        values = np.asarray(
            [
                pd.to_numeric(
                    row.get(column),
                    errors="coerce",
                )
                for column in LINEAR_ACCEL_COLUMNS
            ],
            dtype=float,
        )

        if not np.isfinite(values).all():
            return None

        quaternion = self.orientation_quaternion(row)

        if quaternion is not None:
            aligned = quat_rotate(quaternion, values)
        else:
            if self.aligner is None:
                return None

            aligned = self.aligner.align_single(values)

        aligned = np.asarray(aligned, dtype=float)

        if aligned.shape != (3,) or not np.isfinite(aligned).all():
            return None

        # World ENU:
        # x -> East
        # y -> North
        # z -> Up
        return aligned[:2]

    # ------------------------------------------------------------------ #
    # Quaternion helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def orientation_quaternion(
        row: pd.Series,
    ) -> Optional[np.ndarray]:
        values = np.asarray(
            [
                pd.to_numeric(
                    row.get(column),
                    errors="coerce",
                )
                for column in ORIENTATION_QUATERNION_COLUMNS
            ],
            dtype=float,
        )

        if not np.isfinite(values).all():
            return None

        norm = np.linalg.norm(values)

        if norm < 1e-12:
            return None

        return values / norm

    def _transform_with_orientation(
        self,
        df: pd.DataFrame,
    ) -> np.ndarray:
        """
        Rotate every linear acceleration sample using its orientation
        quaternion.

        Quaternion convention comes from orientation_estimation.py:
        scalar-first (w, x, y, z), device -> world.
        """
        acceleration = np.column_stack(
            [
                pd.to_numeric(
                    df[c],
                    errors="coerce",
                ).to_numpy(dtype=float)
                for c in LINEAR_ACCEL_COLUMNS
            ]
        )

        quaternion = np.column_stack(
            [
                pd.to_numeric(
                    df[c],
                    errors="coerce",
                ).to_numpy(dtype=float)
                for c in ORIENTATION_QUATERNION_COLUMNS
            ]
        )

        result = np.full_like(acceleration, np.nan, dtype=float)

        valid = (
            np.isfinite(acceleration).all(axis=1)
            & np.isfinite(quaternion).all(axis=1)
        )

        for i in np.flatnonzero(valid):
            q = quaternion[i]
            q_norm = np.linalg.norm(q)

            if q_norm < 1e-12:
                continue

            result[i] = quat_rotate(
                q / q_norm,
                acceleration[i],
            )

        return result