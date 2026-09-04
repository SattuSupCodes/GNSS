"""High-level dataset access for the team.

The DatasetManager hides IO-VNBD internals and the on-disk layout so that
Tanishk (models) and Shatakshi (navigation/fusion) can do:

    from src.data.dataset_manager import DatasetManager
    dm = DatasetManager("data/raw", "data/processed")
    trips = dm.list_trips()
    trip = dm.load_processed_trip("vw16b")          # -> TripData
    meta  = dm.get_trip_metadata("vw16b")

Processed data is read from parquet files in the processed root. If no
processed file exists, the manager falls back to extracting from the raw IO-VNBD
data (smartphone-only, canonical schema). This keeps the API stable even before
the full preprocessing pipeline has run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .data_schema import TripData, TripMetadata
from .io_vnbd_loader import IOVNBDDataset, SyncStatus, detect_sync_status
from .smartphone_extractor import SmartphoneExtractor


class DatasetManager:
    """Simple, stable interface to trips, metadata, raw and processed data."""

    def __init__(
        self,
        raw_root: str,
        processed_root: str,
        split_root: Optional[str] = None,
    ):
        self.raw_root = Path(raw_root).expanduser().resolve()
        self.processed_root = Path(processed_root).expanduser().resolve()
        self.split_root = (
            Path(split_root).expanduser().resolve()
            if split_root
            else self.processed_root / ".." / ".." / "data"
        )

        self.dataset = IOVNBDDataset(str(self.raw_root))
        self.extractor = SmartphoneExtractor(self.dataset)
        self._processed_index: Optional[Dict[str, Path]] = None

    # ------------------------------------------------------------------ #
    # Discovery                                                          #
    # ------------------------------------------------------------------ #

    def list_trips(self, sync_status: Optional[SyncStatus] = None) -> List[str]:
        """List all available smartphone trip ids."""
        return self.extractor.list_trips(sync_status)

    def list_processed_files(self) -> List[Path]:
        """List parquet/pickle processed trip files under the processed root."""
        if self._processed_index is not None:
            return list(self._processed_index.values())
        if not self.processed_root.is_dir():
            return []
        files = sorted(self.processed_root.rglob("*.parquet"))
        self._processed_index = {p.stem: p for p in files}
        return files

    def list_processed_trips(self) -> List[str]:
        """Trip ids that have processed parquet files."""
        return sorted(p.stem for p in self.list_processed_files())

    # ------------------------------------------------------------------ #
    # Loading                                                            #
    # ------------------------------------------------------------------ #

    def load_raw_trip(self, trip_id: str) -> "pd.DataFrame":
        """Load the smartphone-only canonical frame directly from raw."""
        return self.extractor.extract_trip(trip_id).data

    def load_processed_trip(self, trip_id: str) -> TripData:
        """Load a processed trip.

        Prefers the processed parquet file. Falls back to extracting from raw
        IO-VNBD (canonical smartphone-only schema) when no processed file
        exists. Raises FileNotFoundError when the trip is unknown.
        """
        processed_path = self._find_processed(trip_id)
        if processed_path is not None:
            df = pd.read_parquet(processed_path)
            meta = self._meta_from_processed(df, trip_id, processed_path)
            return TripData(trip_id=trip_id, metadata=meta, data=df)
        if trip_id not in self.extractor.list_trips():
            raise FileNotFoundError(
                f"Unknown trip '{trip_id}'. Available: "
                f"{self.extractor.list_trips()[:5]} ..."
            )
        return self.extractor.extract_trip(trip_id)

    def load_processed_trips(self) -> List[TripData]:
        return [self.load_processed_trip(t) for t in self.list_processed_trips()]

    def get_trip_metadata(self, trip_id: str) -> TripMetadata:
        return self.load_processed_trip(trip_id).metadata

    def get_metadata_table(self) -> "pd.DataFrame":
        """A DataFrame of trip metadata for all processed trips."""
        rows = []
        for t in self.list_processed_trips():
            try:
                rows.append(self.load_processed_trip(t).metadata.to_dict())
            except Exception:  # noqa: BLE001 - tolerate single bad trip
                continue
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Validation                                                         #
    # ------------------------------------------------------------------ #

    def validate(self) -> Dict[str, object]:
        """Lightweight self-check; returns a status dict, never raises."""
        smartphone_files = len(self.dataset.list_smartphone_files())
        vehicle_files = len(self.dataset.list_vehicle_files())
        processed = len(self.list_processed_files())
        return {
            "raw_root": str(self.raw_root),
            "smartphone_files": smartphone_files,
            "vehicle_files": vehicle_files,
            "trip_ids": len(self.extractor.list_trips()),
            "processed_files": processed,
            "ok": smartphone_files > 0,
        }

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def _find_processed(self, trip_id: str) -> Optional[Path]:
        for f in self.list_processed_files():
            if f.stem.lower() == trip_id.lower():
                return f
        return None

    @staticmethod
    def _meta_from_processed(
        df: pd.DataFrame, trip_id: str, path: Path
    ) -> TripMetadata:
        status = SyncStatus.UNKNOWN
        if "sync_status" in df.columns and len(df):
            try:
                status = SyncStatus(df["sync_status"].iloc[0])
            except ValueError:
                status = SyncStatus.UNKNOWN
        if "timestamp" in df.columns:
            ts = pd.to_numeric(df["timestamp"], errors="coerce").dropna()
        else:
            ts = pd.Series(dtype=float)
        return TripMetadata(
            trip_id=trip_id.lower(),
            sync_status=status,
            source_files=[str(path)],
            n_samples=len(df),
            start_timestamp=float(ts.min()) if len(ts) else None,
            end_timestamp=float(ts.max()) if len(ts) else None,
            has_smartphone_data=True,
        )