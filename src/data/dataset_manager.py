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
    """Simple, stable interface to trips, metadata, raw and processed data.

    Phase 2 additions (calibration + sequences):
      dm.load_calibrated_trip(trip_id)      # calibrated/aligned frame (DataFrame)
      dm.load_split("train")                # long-format window frame (DataFrame)
    Phase 3 additions (GNSS blackouts):
      dm.list_blackout_scenarios()          # scenario ids under data/blackout
      dm.load_blackout_scenario(id)         # masked frame (DataFrame)
      dm.runtime_frame(df) / reference_frame(df)  # runtime vs offline separation
    """

    def __init__(
        self,
        raw_root: str,
        processed_root: str,
        split_root: Optional[str] = None,
        calibrated_root: Optional[str] = None,
        sequences_root: Optional[str] = None,
        blackout_root: Optional[str] = None,
    ):
        self.raw_root = Path(raw_root).expanduser().resolve()
        self.processed_root = Path(processed_root).expanduser().resolve()
        data_dir = self.processed_root.parent  # "<repo>/data"
        self.split_root = (
            Path(split_root).expanduser().resolve()
            if split_root
            else data_dir / "splits"
        )
        self.calibrated_root = (
            Path(calibrated_root).expanduser().resolve()
            if calibrated_root
            else data_dir / "calibrated"
        )
        self.sequences_root = (
            Path(sequences_root).expanduser().resolve()
            if sequences_root
            else data_dir
        )
        self.blackout_root = (
            Path(blackout_root).expanduser().resolve()
            if blackout_root
            else data_dir / "blackout"
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
    # Calibrated trips (Phase 2)                                         #
    # ------------------------------------------------------------------ #

    def calibrated_trips(self) -> List[str]:
        """Trip ids with calibrated parquet files under the calibrated root."""
        if not self.calibrated_root.is_dir():
            return []
        return sorted(
            p.stem.replace("trip_", "")
            for p in self.calibrated_root.glob("trip_*.parquet")
        )

    def load_calibrated_trip(self, trip_id: str) -> "pd.DataFrame":
        """Load a calibrated/aligned trip.

        Prefers ``data/calibrated/trip_<id>.parquet``. When absent, runs the
        Phase 2 calibration pipeline in memory over the processed trip (raw
        columns preserved, calibrated columns appended) so the API works before
        ``scripts/calibrate_dataset.py`` has been run. Raises FileNotFoundError
        when the trip is unknown.
        """
        path = self.calibrated_root / f"trip_{trip_id.lower()}.parquet"
        if path.is_file():
            return pd.read_parquet(path)
        processed = self.load_processed_trip(trip_id)
        from ..calibration.calibration_pipeline import (  # local import to keep data layer import-light
            CalibrationConfig,
            CalibrationPipeline,
        )

        result = CalibrationPipeline(CalibrationConfig()).run(processed.data)
        return result.frame

    # ------------------------------------------------------------------ #
    # Sequences (Phase 2)                                                 #
    # ------------------------------------------------------------------ #

    def load_split(self, split_name: str) -> "pd.DataFrame":
        """Load the long-format window frame for one split.

        Reads ``<sequences_root>/<split_name>/sequences.parquet``; raises when
        it does not exist with a pointer to ``scripts/generate_sequences.py``.
        """
        if split_name not in ("train", "validation", "test"):
            raise ValueError(
                f"split_name must be one of train/validation/test, got {split_name!r}"
            )
        dir_name = {"train": "training", "validation": "validation", "test": "testing"}[split_name]
        path = self.sequences_root / dir_name / "sequences.parquet"
        if not path.is_file():
            raise FileNotFoundError(
                f"Sequences for split '{split_name}' not found at {path}. "
                "Run: python scripts/generate_sequences.py"
            )
        return pd.read_parquet(path)

    def split_assignments(self) -> Dict[str, str]:
        """Trip id -> split map loaded from the Phase 1 split files."""
        from .sequence_generator import load_split_assignments

        return load_split_assignments(self.split_root)

    # ------------------------------------------------------------------ #
    # Blackout datasets (Phase 3)                                        #
    # ------------------------------------------------------------------ #

    def list_blackout_scenarios(self) -> List[str]:
        """Scenario ids with parquet outputs under the blackout root."""
        if not self.blackout_root.is_dir():
            return []
        return sorted(
            p.stem
            for p in self.blackout_root.rglob("*.parquet")
            if not p.stem.endswith("_vehicle_reference")
        )

    def blackout_scenario_path(self, scenario_id: str) -> Optional[Path]:
        if not self.blackout_root.is_dir():
            return None
        for p in self.blackout_root.rglob(f"{scenario_id}.parquet"):
            return p
        return None

    def load_blackout_scenario(self, scenario_id: str) -> "pd.DataFrame":
        """Load a blackout parquet; raises FileNotFoundError when unknown."""
        path = self.blackout_scenario_path(scenario_id)
        if path is None:
            raise FileNotFoundError(
                f"Blackout scenario '{scenario_id}' not found under {self.blackout_root}. "
                "Run: python scripts/create_blackouts.py"
            )
        return pd.read_parquet(path)

    def blackout_scenario_metadata(self, scenario_id: str) -> dict:
        path = self.blackout_root / f"{scenario_id}_metadata.json"
        candidates = list(self.blackout_root.rglob(f"{scenario_id}_metadata.json"))
        if not candidates:
            raise FileNotFoundError(
                f"No metadata for blackout scenario '{scenario_id}'."
            )
        import json

        return json.loads(candidates[0].read_text(encoding="utf-8"))

    def runtime_frame(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Strip ``reference_*`` columns - the frame a runtime model receives."""
        ref_cols = [c for c in df.columns if c.startswith("reference_")]
        return df.drop(columns=ref_cols)

    def reference_frame(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Offline reference columns only (evaluation/ground-truth, never runtime)."""
        ref_cols = [c for c in df.columns if c.startswith("reference_")]
        cols = ["timestamp"] + ref_cols
        return df[[c for c in cols if c in df.columns]]

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