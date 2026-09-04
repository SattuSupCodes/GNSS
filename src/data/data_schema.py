"""Canonical data schema for the Intelligent Dead Reckoning project.

Defines the standardized, machine-readable representation of smartphone sensor
data produced by the Phase 1 pipeline. This schema is the single contract that
downstream modules (ML/DL training, navigation/fusion) consume.

MAINTAINED SEPARATION OF CONCERNS
---------------------------------
The schema distinguishes three kinds of fields:

* SENSOR fields  : runtime inputs only. Everything here is produced by the
                   smartphone (accelerometer, gyroscope, magnetometer, GNSS).
* METADATA       : identifiers and provenance (trip id, source file, status).
* REFERENCE      : offline, evaluation-only values. MUST never be used as a
                   runtime sensor input. Currently optional per-trip vehicle
                   data is kept OUT of the canonical per-sample frame.

Nothing in this schema is a vehicle-side runtime input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class SourceKind(str, Enum):
    """Which side of the IO-VNBD recording a file belongs to."""

    SMARTPHONE = "smartphone"
    VEHICLE = "vehicle"


class SyncStatus(str, Enum):
    """Synchronisation status of a recording."""

    SYNCHRONISED = "synchronised"
    UNSYNCHRONISED = "unsynchronised"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Canonical column names (lower-case, underscores). These are the ONLY names   #
# the rest of Phase 1+ code must use.                                          #
# --------------------------------------------------------------------------- #

# Time
TS_SEC = "timestamp"  # UTC-aware POSIX seconds float (primary time axis)
MS_SINCE_START = "time_since_start_ms"
DATETIME = "datetime"  # pandas native timestamp column (index/assist)

# IMU
ACCEL_X = "accel_x"
ACCEL_Y = "accel_y"
ACCEL_Z = "accel_z"
GYRO_X = "gyro_x"
GYRO_Y = "gyro_y"
GYRO_Z = "gyro_z"
MAG_X = "mag_x"
MAG_Y = "mag_y"
MAG_Z = "mag_z"
GRAV_X = "gravity_x"
GRAV_Y = "gravity_y"
GRAV_Z = "gravity_z"
ORIENT_AZIMUTH = "orientation_azimuth_deg"
ORIENT_PITCH = "orientation_pitch_deg"
ORIENT_ROLL = "orientation_roll_deg"

# GNSS (smartphone GNSS only)
GNSS_LAT = "latitude_deg"
GNSS_LON = "longitude_deg"
GNSS_ALT = "altitude_m"
GNSS_SPEED = "speed_kmh"
GNSS_ACCURACY = "position_accuracy_m"
GNSS_HEADING = "gps_heading_deg"
GNSS_SATELLITES = "gps_satellites"

# Metadata / provenance
TRIP_ID = "trip_id"
SOURCE_FILE = "source_file"
SYNC_STATUS = "sync_status"
DRIVER = "driver"
CATEGORY = "category"
REFERENCE_FLAG = "is_reference"  # True for rows that came from a reference source

# --------------------------------------------------------------------------- #
# Which canonical columns are runtime sensor inputs vs metadata vs reference.  #
# --------------------------------------------------------------------------- #

SENSOR_COLUMNS: Tuple[str, ...] = (
    TS_SEC,
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    GRAV_X,
    GRAV_Y,
    GRAV_Z,
    ORIENT_AZIMUTH,
    ORIENT_PITCH,
    ORIENT_ROLL,
    GNSS_LAT,
    GNSS_LON,
    GNSS_ALT,
    GNSS_SPEED,
    GNSS_ACCURACY,
    GNSS_HEADING,
    GNSS_SATELLITES,
)

METADATA_COLUMNS: Tuple[str, ...] = (
    TRIP_ID,
    SOURCE_FILE,
    SYNC_STATUS,
    DRIVER,
    CATEGORY,
)

REFERENCE_COLUMNS: Tuple[str, ...] = (REFERENCE_FLAG,)

ALL_CANONICAL_COLUMNS: Tuple[str, ...] = (
    tuple(i for i in SENSOR_COLUMNS if i != TS_SEC)
    + (DATETIME, MS_SINCE_START)
    + METADATA_COLUMNS
    + REFERENCE_COLUMNS
)

SUPPORTED_SENSOR_RATE_HZ = 10.0
"""Observed nominal smartphone sampling rate in IO-VNBD (S- files)."""


# --------------------------------------------------------------------------- #
# IO-VNBD source column name -> canonical column name mapping.                #
# Source names are matched case-insensitively and after stripping whitespace. #
# --------------------------------------------------------------------------- #

IOVNBD_SMARTPHONE_COLUMN_MAP: dict = {
    "GPS LATITUDE (DEGREES)": GNSS_LAT,
    "GPS LONGITUDE (DEGREES)": GNSS_LON,
    "GPS ALTITUDE (M)": GNSS_ALT,
    "GPS SPEED (KMH)": GNSS_SPEED,
    "GPS ACCURACY (M)": GNSS_ACCURACY,
    "GPS ORIENTATION (\u00b0)": GNSS_HEADING,
    "GPS SATELLITES IN RANGE": GNSS_SATELLITES,
    "TIME SINCE START (MS)": MS_SINCE_START,
    "ACCELEROMETER X (M/S\u00b2)": ACCEL_X,
    "ACCELEROMETER Y (M/S\u00b2)": ACCEL_Y,
    "ACCELEROMETER Z (M/S\u00b2)": ACCEL_Z,
    "GRAVITY X (M/S\u00b2)": GRAV_X,
    "GRAVITY Y (M/S\u00b2)": GRAV_Y,
    "GRAVITY Z (M/S\u00b2)": GRAV_Z,
    # IO-VNBD uses two naming schemes for gyro + orientation. The newer files
    # use device X/Y/Z and azimuth; the rest label axes Yaw/Pitch/Roll.
    "GYROSCOPE X (RAD/S)": GYRO_X,
    "GYROSCOPE Y (RAD/S)": GYRO_Y,
    "GYROSCOPE Z (RAD/S)": GYRO_Z,
    "GYROSCOPE YAW (RAD/S)": GYRO_X,
    "GYROSCOPE PITCH (RAD/S)": GYRO_Y,
    "GYROSCOPE ROLL (RAD/S)": GYRO_Z,
    "MAGNETIC FIELD X (\u039cT)": MAG_X,
    "MAGNETIC FIELD Y (\u039cT)": MAG_Y,
    "MAGNETIC FIELD Z (\u039cT)": MAG_Z,
    "ORIENTATION (AZIMUTH) (\u00b0)": ORIENT_AZIMUTH,
    "ORIENTATION (YAW) (\u00b0)": ORIENT_AZIMUTH,
    "ORIENTATION (PITCH) (\u00b0)": ORIENT_PITCH,
    "ORIENTATION (ROLL ) (\u00b0)": ORIENT_ROLL,
}


def normalize_source_column(name: str) -> str:
    """Normalize an IO-VNBD source header for canonical lookup.

    Phase 1 observed two encoding quirks that must be repaired here:

    * Degree sign ``\u00b0`` is stored as UTF-8 bytes ``0xC2 0xB0`` in an
      otherwise cp1252 file, so pandas reads the string ``'\\u00c2\\u00b0'``
      ("Â°", two characters). We collapse that pair back to ``\u00b0``.
    * Greek mu ``\u03bc`` is stored as UTF-8 bytes ``0xCE 0xBC``, read as
      ``'\\u00ce\\u00bc'`` ("Î¼"). Collapsed back to ``\u03bc`` and upper-cased
      to ``\u039c`` (capital MU) to match the unit "ΜT".

    After those repairs the header is upper-cased and whitespace-collapsed, then
    remaining single-byte variants (micro sign ``\u00b5``) are canonicalized so
    the result matches a key in :data:`IOVNBD_SMARTPHONE_COLUMN_MAP`.
    """
    n = " ".join(str(name).split())
    n = n.replace("\u00c2\u00b0", "\u00b0")
    n = n.replace("\u00ce\u00bc", "\u03bc")
    n = n.upper()
    n = n.replace("\u00b5", "\u039c")
    n = n.replace("\u03bc", "\u039c")
    return n


def canonical_columns_present(columns_upper: iter) -> List[str]:
    """Return the canonical names whose source columns exist in a header."""
    found = []
    for c in columns_upper:
        c = normalize_source_column(c)
        if c in IOVNBD_SMARTPHONE_COLUMN_MAP:
            found.append(IOVNBD_SMARTPHONE_COLUMN_MAP[c])
    return found


# --------------------------------------------------------------------------- #
# Typed container for one processed trip.                                     #
# --------------------------------------------------------------------------- #


@dataclass
class TripMetadata:
    """Non-tabular metadata for a single trip."""

    trip_id: str
    sync_status: SyncStatus
    driver: Optional[str] = None
    category: Optional[str] = None
    source_files: List[str] = field(default_factory=list)
    n_samples: Optional[int] = None
    start_timestamp: Optional[float] = None
    end_timestamp: Optional[float] = None
    nominal_rate_hz: Optional[float] = None
    has_smartphone_data: bool = True
    has_vehicle_data: bool = False

    def to_dict(self) -> dict:
        d = {
            "trip_id": self.trip_id,
            "sync_status": self.sync_status.value,
            "driver": self.driver,
            "category": self.category,
            "source_files": list(self.source_files),
            "n_samples": self.n_samples,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "nominal_rate_hz": self.nominal_rate_hz,
            "has_smartphone_data": self.has_smartphone_data,
            "has_vehicle_data": self.has_vehicle_data,
        }
        return d


@dataclass
class TripData:
    """A processed trip: plain tabular data + metadata."""

    trip_id: str
    metadata: TripMetadata
    data: "object"  # pandas DataFrame (canonical schema)

    def __len__(self) -> int:
        return 0 if self.data is None else len(self.data)