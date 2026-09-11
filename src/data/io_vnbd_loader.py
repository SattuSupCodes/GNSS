"""Loader for the IO-VNBD dataset.

Discovers and reads IO-VNBD CSV files (smartphone `S-*` and vehicle `V-*`),
remaps raw headers to the canonical schema, parses timestamps, and produces
smartphone-only trip frames.

Design rules enforced here:

* Never treat vehicle data as a runtime input. Vehicle files can be loaded
  explicitly for reference purposes, flagged with ``is_reference=True``.
* Do not hardcode filenames; discovery is driven by walking the raw root.
* Fail gracefully (raise ``DatasetNotFoundError``/``IOVNBDError``) when data is
  missing or is an unresolved Git-LFS pointer, never fabricate data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pandas as pd

from .data_schema import (
    IOVNBD_SMARTPHONE_COLUMN_MAP,
    DATETIME,
    GRAV_X,
    GRAV_Y,
    GRAV_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    MS_SINCE_START,
    ORIENT_AZIMUTH,
    ORIENT_PITCH,
    ORIENT_ROLL,
    SOURCE_FILE,
    SYNC_STATUS,
    TRIP_ID,
    TS_SEC,
    TripMetadata,
    SyncStatus,
    normalize_source_column,
)


class IOVNBDError(Exception):
    """Base error for IO-VNBD loading problems."""


class DatasetNotFoundError(IOVNBDError):
    """Raised when required dataset directories/files are absent."""


class UnresolvedLFSFileError(IOVNBDError):
    """Raised when a CSV on disk is an unresolved Git LFS pointer."""


class UnsupportedSourceError(IOVNBDError):
    """Raised when a file type/prefixed name is not understood."""


DATE_COL_RAW = "DATE (YYYY-MO-DD HH-MI-SS_SSS)"
LFS_POINTER_THRESHOLD_BYTES = 1000
ENCODING = "cp1252"

DRIVER_BY_FOLDER: Dict[str, Optional[str]] = {
    "M (DRIVER B)": "B",
    "S (DRIVER A)": "A",
    "Y (DRIVER D)": "D",
    "VF (DRIVER E)": "E",
    "VTA (DRIVER E)": "E",
    "VTB (DRIVER E)": "E",
    "VW (DRIVER E)": "E",
    "ST (DRIVER C)": "C",
}


class IOVNBDDataset:
    """Facade over the local IO-VNBD raw root."""

    def __init__(self, raw_root: str):
        self.raw_root = Path(raw_root).expanduser().resolve()
        if not self.raw_root.is_dir():
            raise DatasetNotFoundError(
                f"IO-VNBD raw root not found: {self.raw_root}"
            )
        # Support both a fresh clone (data/raw/IO-VNBD/...) and a flattened
        # layout where the datasets sit directly in data/raw/....
        root = (
            self.raw_root / "IO-VNBD"
            if (self.raw_root / "IO-VNBD").is_dir()
            else self.raw_root
        )
        self._root = root
        self._sync_root = root / "Synchronised V abd S datasets"
        self._unsync_root = root / "Unsynchronised V and S Dataset"

    # ------------------------------------------------------------------ #
    # Discovery                                                          #
    # ------------------------------------------------------------------ #

    def list_csv_files(self) -> List[Path]:
        """All CSV files under the raw root, sorted."""
        return sorted(self._root.rglob("*.csv"))

    def list_smartphone_files(self) -> List[Path]:
        """All smartphone (``S-*.csv``) files under the raw root."""
        return sorted(p for p in self.list_csv_files() if p.name.startswith("S-"))

    def list_vehicle_files(self) -> List[Path]:
        """All vehicle (``V-*.csv``) files under the raw root."""
        return sorted(p for p in self.list_csv_files() if p.name.startswith("V-"))

    def smartphone_trip_ids(self) -> List[str]:
        """Unique lower-cased smartphone trip ids across the whole root."""
        ids = set()
        for p in self.list_smartphone_files():
            ids.add(self._trip_id_from_path(p))
        return sorted(ids)

    def smartphone_file_for_trip(
        self, trip_id: str, sync_status: Optional[SyncStatus] = None
    ) -> Optional[Path]:
        """Locate an S-* file for a trip id (case-insensitive).

        If ``sync_status`` is given (SYNCHRONISED / UNSYNCHRONISED), restrict the
        search to that subtree. Returns None when not found.
        """
        trip_l = trip_id.lower()
        roots: List[Path]
        if sync_status == SyncStatus.SYNCHRONISED:
            roots = [self._sync_root]
        elif sync_status == SyncStatus.UNSYNCHRONISED:
            roots = [self._unsync_root]
        else:
            roots = [self._sync_root, self._unsync_root]
        for root in roots:
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*.csv")):
                if (
                    p.name.startswith("S-")
                    and p.name[2:].rstrip(".csv").lower() == trip_l
                ):
                    return p
        return None

    def vehicle_file_for_trip(
        self, trip_id: str, sync_status: Optional[SyncStatus] = None
    ) -> Optional[Path]:
        trip_l = trip_id.lower()
        roots = (
            [self._sync_root, self._unsync_root]
            if sync_status is None
            else (
                [self._sync_root]
                if sync_status == SyncStatus.SYNCHRONISED
                else [self._unsync_root]
            )
        )
        for root in roots:
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*.csv")):
                if (
                    p.name.startswith("V-")
                    and p.name[2:].rstrip(".csv").lower() == trip_l
                ):
                    return p
        return None

    @staticmethod
    def _trip_id_from_path(p: Path) -> str:
        return p.name[2:].rstrip(".csv").lower()

    # ------------------------------------------------------------------ #
    # Existence + validation                                              #
    # ------------------------------------------------------------------ #

    def has_smartphone_data(self) -> bool:
        return len(self.list_smartphone_files()) > 0

    def check_smartphone_data_available(self) -> None:
        """Raise a clear error if no real smartphone data is available."""
        if not self.has_smartphone_data():
            raise DatasetNotFoundError(
                "No smartphone (S-*.csv) files found under: " + str(self.raw_root)
            )


def _looks_like_lfs_pointer(path: Path) -> bool:
    if path.stat().st_size <= LFS_POINTER_THRESHOLD_BYTES:
        with path.open("rb") as fh:
            head = fh.read(80)
        return head.startswith(b"version https://git-lfs.github.com/spec/v1")
    return False


def _driver_from_folder(path: Path) -> Optional[str]:
    for part in path.parts:
        key = part.upper()
        if key in DRIVER_BY_FOLDER:
            return DRIVER_BY_FOLDER[key]
    return None


def _category_from_path(path: Path) -> Optional[str]:
    for part in path.parts:
        up = part.upper()
        if up.startswith("M (") or up in ("S (DRIVER A)", "Y (DRIVER D)"):
            pass
    # Primary id prefix is the best category signal.
    name = path.name
    if name.startswith("S-"):
        inner = name[2:].rstrip(".csv").lower()
        for prefix in ("vta", "vtb", "vw", "vfa", "vfb"):
            if inner.startswith(prefix):
                return prefix.upper()
        if inner.startswith("s"):
            return "S"
        if inner.startswith("m"):
            return "M"
        if inner.startswith("y"):
            return "Y"
    return None


def detect_sync_status(path: Path) -> SyncStatus:
    spath = str(path)
    if "Synchronised" in spath:
        return SyncStatus.SYNCHRONISED
    if "Unsynchronised" in spath:
        return SyncStatus.UNSYNCHRONISED
    return SyncStatus.UNKNOWN


def load_smartphone_csv(
    path: Path, trip_id: Optional[str] = None
) -> pd.DataFrame:
    """Load a single smartphone CSV into canonical column naming.

    Returns a DataFrame with canonical sensor columns plus raw timestamp
    columns. Timestamps are parsed into the ``timestamp`` POSIX-seconds column
    and a ``datetime`` column. ``trip_id`` / ``source_file`` / ``sync_status``
    are attached as metadata columns.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"File does not exist: {path}")
    if _looks_like_lfs_pointer(path):
        raise UnresolvedLFSFileError(
            f"'{path.name}' is an unresolved Git LFS pointer (no real data). "
            "Clone the dataset with Git LFS enabled (see docs/dataset.md)."
        )
    try:
        df = pd.read_csv(path, encoding=ENCODING)
    except Exception as exc:  # noqa: BLE001 - surface with context
        raise IOVNBDError(f"Failed to read CSV {path}: {exc}") from exc

    df = _remap_columns(df, path)
    df = _attach_timestamps(df, path)
    df = _coerce_sensor_dtypes(df, path)
    df = _attach_metadata(df, path, trip_id=trip_id)
    return df


def load_vehicle_csv(
    path: Path, trip_id: Optional[str] = None
) -> pd.DataFrame:
    """Load a vehicle CSV.

    Vehicle data is reference-only. This method performs NO column remapping to
    sensor names and attaches ``is_reference=True`` so downstream code can
    never mistake it for runtime sensor input. Raises if the file is missing or
    an LFS pointer.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"File does not exist: {path}")
    if _looks_like_lfs_pointer(path):
        raise UnresolvedLFSFileError(
            f"'{path.name}' is an unresolved Git LFS pointer."
        )
    try:
        df = pd.read_csv(path, encoding=ENCODING)
    except Exception as exc:  # noqa: BLE001
        raise IOVNBDError(f"Failed to read vehicle CSV {path}: {exc}") from exc

    # Vehicle files carry 'Time Since Start of Day (seconds)'; promote it to the
    # canonical timestamp so reference traces share a common time axis with the
    # smartphone stream (relative alignment is what synchronization needs).
    for col in df.columns:
        if normalize_source_column(col) == "TIME SINCE START OF DAY (SECONDS)":
            df[TS_SEC] = pd.to_numeric(df[col], errors="coerce")
            break
    if TS_SEC not in df.columns:
        df[TS_SEC] = float("nan")
    df["is_reference"] = True
    if trip_id is not None:
        df[TRIP_ID] = trip_id
    df[SOURCE_FILE] = str(path)
    df[SYNC_STATUS] = detect_sync_status(path).value
    return df


def _remap_columns(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Rename raw S-file headers to canonical sensor names.

    Returns a frame with only canonical sensor columns plus the raw date/time
    source columns that have no canonical equivalent yet.
    """
    rename: Dict[str, str] = {}
    for col in df.columns:
        norm = normalize_source_column(col)
        if norm in IOVNBD_SMARTPHONE_COLUMN_MAP:
            rename[col] = IOVNBD_SMARTPHONE_COLUMN_MAP[norm]
        elif norm in (
            "DATE (YYYY-MO-DD HH-MI-SS_SSS)",
            "DATE (YYYY-MO-DD HH-MI-SS_SSS",  # 2 files have a truncated header
        ):
            rename[col] = "raw_date_str"
    mapped = df.rename(columns=rename)

    # Retain only recognized canonical sensor columns + raw date string.
    keep = list(dict.fromkeys(rename.values()))
    if set(keep).issubset(set(df.columns)):
        mapped = mapped[keep]
    else:
        mapped = mapped[[c for c in keep if c in mapped.columns]]
    return mapped


def _attach_timestamps(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Parse the raw date string + ms-since-start into canonical time columns.

    The source date column looks like ``2020-01-08 17:42:16:002`` (a ':' before
    the milliseconds). We convert the final ':xxx' to '.xxx' and parse with
    pandas. Also adds ms-since-start if present. Returns a copy with new
    columns.
    """
    out = df.copy()
    if "raw_date_str" in out.columns:
        raw = out["raw_date_str"].astype(str).str.strip()
        fixed = raw.str.replace(r":(\d{3})$", r".\1", regex=True)
        dt = pd.to_datetime(fixed, format="%Y-%m-%d %H:%M:%S.%f", errors="coerce")
        out[DATETIME] = dt
        # POSIX epoch seconds
        out[TS_SEC] = dt.map(
            lambda x: x.timestamp() if pd.notna(x) else float("nan")
        ).astype(float)
    else:
        # No date column: try ms-since-start as the primary time if present,
        # else leave timestamp as NaN (all-NaN column is created for schema
        # consistency).
        if MS_SINCE_START in out.columns:
            out[TS_SEC] = pd.to_numeric(out[MS_SINCE_START], errors="coerce") / 1000.0
        else:
            out[TS_SEC] = float("nan")
    if MS_SINCE_START not in out.columns:
        out[MS_SINCE_START] = float("nan")
    if DATETIME not in out.columns:
        out[DATETIME] = pd.NaT
    return out


def _coerce_sensor_dtypes(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Force canonical sensor/gnss columns to float.

    The raw files store ``gps_satellites`` as strings like ``"25 / 25"``
    (usable / in-range); we keep the first integer so the column is numeric and
    compatible with the canonical schema. All other canonical numeric columns
    are coerced with errors='coerce' so non-numeric placeholders become NaN
    instead of crashing downstream analysis.
    """
    out = df.copy()
    if "gps_satellites" in out.columns:
        as_str = out["gps_satellites"].astype("string")
        num = as_str.str.split("/", n=1, regex=False).str[0]
        out["gps_satellites"] = pd.to_numeric(num, errors="coerce").astype(float)
    numeric_cols = [
        c
        for c in out.columns
        if c
        not in ("raw_date_str", TRIP_ID, SOURCE_FILE, "is_reference", SYNC_STATUS)
    ]
    for c in numeric_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    return out


def _attach_metadata(
    df: pd.DataFrame, path: Path, trip_id: Optional[str] = None
) -> pd.DataFrame:
    out = df.copy()
    tid = trip_id if trip_id is not None else path.name[2:].rstrip(".csv")
    out[TRIP_ID] = tid.lower()
    out[SOURCE_FILE] = str(path)
    out[SYNC_STATUS] = detect_sync_status(path).value
    return out


def iter_smartphone_trips(
    dataset: IOVNBDDataset,
    sync_status: Optional[SyncStatus] = None,
) -> Iterator[Tuple[str, Path, SyncStatus]]:
    """Yield (trip_id, path, sync_status) for every smartphone file."""
    for p in dataset.list_smartphone_files():
        status = detect_sync_status(p)
        if sync_status is not None and status != sync_status:
            continue
        yield dataset._trip_id_from_path(p), p, status


def load_smartphone_trip(
    dataset: IOVNBDDataset, trip_id: str, sync_status: Optional[SyncStatus] = None
) -> Tuple[pd.DataFrame, TripMetadata]:
    """Load one smartphone trip as a canonical DataFrame + metadata.

    Raises :class:`DatasetNotFoundError` when the trip has no smartphone file.
    """
    path = dataset.smartphone_file_for_trip(trip_id, sync_status)
    if path is None:
        raise DatasetNotFoundError(
            f"No smartphone file found for trip '{trip_id}'"
            + (f" with status {sync_status.value}" if sync_status else "")
        )
    df = load_smartphone_csv(path, trip_id=trip_id)
    meta = TripMetadata(
        trip_id=trip_id.lower(),
        sync_status=detect_sync_status(path),
        driver=_driver_from_folder(path.parent),
        category=_category_from_path(path),
        source_files=[str(path)],
        n_samples=len(df),
        has_smartphone_data=True,
        has_vehicle_data=dataset.vehicle_file_for_trip(trip_id) is not None,
    )
    dt = pd.to_datetime(df[DATETIME], errors="coerce")
    valid = dt.dropna()
    if len(valid):
        meta.start_timestamp = float(valid.min().timestamp())
        meta.end_timestamp = float(valid.max().timestamp())
    return df, meta