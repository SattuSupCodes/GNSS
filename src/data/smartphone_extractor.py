"""Smartphone-only extraction layer for IO-VNBD.

Turns raw IO-VNBD into a clean smartphone-only canonical dataset. This module
is the single place where "which columns are runtime smartphone inputs" is
answered: it selects exactly the canonical sensor columns from the loaded
IO-VNBD smartphone files and nothing else.

The layer is kept independent of IO-VNBD internals, so future live Android
sensor streams can be mapped to the same canonical output.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import pandas as pd

from .data_schema import (
    ALL_CANONICAL_COLUMNS,
    DATETIME,
    MS_SINCE_START,
    SENSOR_COLUMNS,
    SOURCE_FILE,
    SYNC_STATUS,
    TRIP_ID,
    TripData,
    TripMetadata,
    SyncStatus,
)
from .io_vnbd_loader import (
    IOVNBDDataset,
    UnresolvedLFSFileError,
    _category_from_path,
    _driver_from_folder,
    load_smartphone_csv,
    load_smartphone_trip,
    detect_sync_status,
)


# Canonical ordering for extracted frames: time first, then IMU, GNSS,
# orientation, then provenance columns (which are metadata, not sensors).
_EXTRACT_ORDER = (
    "timestamp",
    DATETIME,
    MS_SINCE_START,
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "mag_x",
    "mag_y",
    "mag_z",
    "gravity_x",
    "gravity_y",
    "gravity_z",
    "orientation_azimuth_deg",
    "orientation_pitch_deg",
    "orientation_roll_deg",
    "latitude_deg",
    "longitude_deg",
    "altitude_m",
    "speed_kmh",
    "position_accuracy_m",
    "gps_heading_deg",
    "gps_satellites",
    TRIP_ID,
    SOURCE_FILE,
    SYNC_STATUS,
)


def extract_smartphone_frame(
    raw_frame: pd.DataFrame,
    trip_id: str,
    source_file: str,
    sync_status: SyncStatus,
) -> pd.DataFrame:
    """Select only smartphone sensor columns from a raw/loaded frame.

    Parameters
    ----------
    raw_frame : pandas.DataFrame
        A frame loaded by :mod:`src.data.io_vnbd_loader` (or anything with
        canonical column names).
    trip_id, source_file, sync_status
        Provenance values attached as metadata columns.

    Returns a DataFrame containing ONLY canonical smartphone sensor columns and
    provenance metadata. Reference/vehicle columns, if present, are dropped.
    """
    cols = [c for c in _EXTRACT_ORDER if c in raw_frame.columns]
    out = raw_frame[cols].copy()
    out[TRIP_ID] = trip_id
    out[SOURCE_FILE] = source_file
    out[SYNC_STATUS] = sync_status.value
    return out


class SmartphoneExtractor:
    """Extract smartphone-only canonical trips from an IO-VNBD dataset.

    Examples
    --------
    >>> ds = IOVNBDDataset("data/raw")
    >>> ex = SmartphoneExtractor(ds)
    >>> trips = ex.list_trips()
    >>> frame, meta = ex.extract_trip("vw16b")
    """

    def __init__(self, dataset: IOVNBDDataset):
        self.dataset = dataset

    def list_trips(self, sync_status: Optional[SyncStatus] = None) -> List[str]:
        """List available smartphone trip ids (optionally filtered by status)."""
        return self.dataset.smartphone_trip_ids()

    def extract_trip(
        self, trip_id: str, sync_status: Optional[SyncStatus] = None
    ) -> TripData:
        """Extract one smartphone trip into canonical smartphone-only form."""
        if not self.dataset.has_smartphone_data():
            raise UnresolvedLFSFileError(
                "No smartphone data available. If you see Git LFS pointers, "
                "clone the dataset with Git LFS enabled; see docs/dataset.md."
            )
        path = self.dataset.smartphone_file_for_trip(trip_id, sync_status)
        if path is None:
            raise FileNotFoundError(
                f"No smartphone file found for trip '{trip_id}'"
            )
        df = load_smartphone_csv(path, trip_id=trip_id)
        status = detect_sync_status(path)
        trip_id_l = trip_id.lower()
        out = extract_smartphone_frame(
            df, trip_id_l, str(path), status
        )
        meta = TripMetadata(
            trip_id=trip_id_l,
            sync_status=status,
            driver=_driver_from_folder(path.parent),
            category=_category_from_path(path),
            source_files=[str(path)],
            n_samples=len(out),
            has_smartphone_data=True,
            has_vehicle_data=self.dataset.vehicle_file_for_trip(trip_id) is not None,
        )
        return TripData(trip_id=trip_id_l, metadata=meta, data=out)

    def extract_all_trips(
        self, sync_status: Optional[SyncStatus] = None
    ) -> List[TripData]:
        """Extract all smartphone trips (may be slow; use for small studies)."""
        result = []
        for tid in self.list_trips(sync_status):
            result.append(self.extract_trip(tid, sync_status))
        return result