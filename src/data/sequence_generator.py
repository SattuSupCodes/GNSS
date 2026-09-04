"""Fixed-length temporal window generation over processed/calibrated trips.

Purpose
-------
Turn continuous per-sample trips into fixed-length windows for ML/navigation
consumers (Tanishk) without ever mixing two trips in one window.

Leakage policy (hard rules)
---------------------------
* Windows are generated **per trip**: the first and last window of a trip are
  computed from that trip's rows only, so a window can never span two trips.
* Splits are trip-level (see ``src/data/dataset_splitter.py``): sequence
  generation happens **inside** each split independently. A trip belongs to
  exactly one split; therefore every window inherits its trip's split.
* No random row-level splitting, ever.

Output format
-------------
:meth:`windows_to_frame` returns a long DataFrame with one row per sample,
grouped by ``sequence_id``; each group is exactly ``window_rows`` long (when
``drop_incomplete_tail=True``). Join keys and provenance are repeated on every
row so consumers can ``groupby("sequence_id")`` and read clean fixed-length
blocks:

    sequence_id, trip_id, split, window_index,
    window_start_timestamp, window_stop_timestamp, sample_in_window,
    + the selected sensor/metadata columns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .data_schema import TRIP_ID

SPLIT_ORDER = ("train", "validation", "test")

# Output directory names per split label (ML consumers read "training"/"testing").
SPLIT_TO_DIR = {"train": "training", "validation": "validation", "test": "testing"}


@dataclass
class WindowConfig:
    """Window geometry + column selection."""

    window_rows: int = 100
    stride_rows: int = 100
    drop_incomplete_tail: bool = True
    columns: Optional[List[str]] = None  # None = carry all available columns
    sequence_id_prefix: str = "win"

    def __post_init__(self):
        if self.window_rows < 1:
            raise ValueError(f"window_rows must be >= 1, got {self.window_rows}")
        if self.stride_rows < 1:
            raise ValueError(f"stride_rows must be >= 1, got {self.stride_rows}")


@dataclass
class SequenceWindow:
    """One fixed-length window extracted from a single trip."""

    sequence_id: str
    trip_id: str
    split: Optional[str]
    window_index: int
    start_timestamp: float
    stop_timestamp: float
    data: pd.DataFrame = field(repr=False)

    def to_meta(self) -> Dict[str, object]:
        return {
            "sequence_id": self.sequence_id,
            "trip_id": self.trip_id,
            "split": self.split,
            "window_index": self.window_index,
            "start_timestamp": self.start_timestamp,
            "stop_timestamp": self.stop_timestamp,
            "n_samples": int(len(self.data)),
        }


def generate_windows(
    df: pd.DataFrame,
    trip_id: str,
    config: WindowConfig,
    split: Optional[str] = None,
) -> List[SequenceWindow]:
    """Generate fixed-length windows from a single trip frame.

    The frame is sorted by ``timestamp`` if the column exists; windows are
    contiguous blocks of ``window_rows`` stride-stride apart **within this trip
    only**. Incomplete tails are dropped unless ``drop_incomplete_tail`` is
    False (then a final shorter window is appended).
    """
    if df is None or len(df) == 0:
        return []
    cfg = config
    frame = df.copy()
    if "timestamp" in frame.columns:
        frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    columns = cfg.columns or list(frame.columns)
    columns = [c for c in columns if c in frame.columns]
    frame = frame[columns]

    n = len(frame)
    windows: List[SequenceWindow] = []
    start = 0
    index = 0
    while start < n:
        end = start + cfg.window_rows
        if end > n:
            if cfg.drop_incomplete_tail:
                break
            end = n
        w = frame.iloc[start:end].reset_index(drop=True)
        t0 = float(w["timestamp"].iloc[0]) if "timestamp" in w.columns else float("nan")
        t1 = float(w["timestamp"].iloc[-1]) if "timestamp" in w.columns else float("nan")
        seq = f"{cfg.sequence_id_prefix}_{trip_id}_{index:04d}"
        windows.append(
            SequenceWindow(
                sequence_id=seq,
                trip_id=trip_id,
                split=split,
                window_index=index,
                start_timestamp=t0,
                stop_timestamp=t1,
                data=w,
            )
        )
        index += 1
        start += cfg.stride_rows
    return windows


def generate_windows_for_trips(
    trips: Dict[str, pd.DataFrame],
    config: WindowConfig,
    split_assignment: Optional[Dict[str, str]] = None,
    splits: Sequence[str] = SPLIT_ORDER,
) -> List[SequenceWindow]:
    """Generate windows across many trips, keeping each trip's windows intact.

    ``split_assignment`` maps trip id -> split name; windows inherit it. When a
    trip id is not in the assignment it is skipped (prevents leakage-by-omission
    from silently changing an intended split).
    """
    windows: List[SequenceWindow] = []
    for trip_id, frame in trips.items():
        split = split_assignment.get(trip_id) if split_assignment else None
        if split_assignment is not None and split is None:
            continue
        if split_assignment is not None and split not in splits:
            continue
        windows.extend(generate_windows(frame, trip_id, config, split=split))
    return windows


def windows_to_frame(windows: Sequence[SequenceWindow]) -> pd.DataFrame:
    """Long-format frame: one row per sample, grouped by ``sequence_id``.

    Adds ``sequence_id``, ``trip_id``, ``split``, ``window_index``,
    ``window_start_timestamp``, ``window_stop_timestamp`` and
    ``sample_in_window`` provenance columns to each window's data.
    """
    parts = []
    for w in windows:
        d = w.data.copy()
        d["sequence_id"] = w.sequence_id
        d["trip_id"] = w.trip_id
        d["split"] = w.split
        d["window_index"] = w.window_index
        d["window_start_timestamp"] = w.start_timestamp
        d["window_stop_timestamp"] = w.stop_timestamp
        d["sample_in_window"] = np.arange(len(d))
        parts.append(d)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    seq_first = ["sequence_id", "trip_id", "split", "window_index",
                 "window_start_timestamp", "window_stop_timestamp", "sample_in_window"]
    rest = [c for c in out.columns if c not in seq_first]
    return out[seq_first + rest]


def group_windows_by_split(
    windows: Sequence[SequenceWindow],
) -> Dict[str, List[SequenceWindow]]:
    out: Dict[str, List[SequenceWindow]] = {s: [] for s in SPLIT_ORDER}
    for w in windows:
        if w.split in out:
            out[w.split].append(w)
    return out


def load_split_assignments(split_root: Path) -> Dict[str, str]:
    """Read Phase 1 trip-level split files into ``{trip_id: split}``.

    Expected files (see ``configs/data_config.yaml``): ``train_trips.txt``,
    ``validation_trips.txt``, ``test_trips.txt`` inside ``split_root``.
    """
    assignment: Dict[str, str] = {}
    for split, fname in (
        ("train", "train_trips.txt"),
        ("validation", "validation_trips.txt"),
        ("test", "test_trips.txt"),
    ):
        p = Path(split_root) / fname
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            tid = line.strip()
            if tid:
                assignment[tid.lower()] = split
    return assignment


def write_sequences(
    windows: Sequence[SequenceWindow],
    output_root: Path,
    splits: Sequence[str] = SPLIT_ORDER,
    split_to_dir: Dict[str, str] = SPLIT_TO_DIR,
) -> Dict[str, int]:
    """Write one Parquet per split (``training/sequences.parquet`` etc.).

    Returns ``{split: n_windows}``. The long-format frame
    (:meth:`windows_to_frame`) is used so consumers get fixed-length,
    groupable blocks. Output directory per split follows ``split_to_dir``
    (default: ``train -> training``, ``test -> testing``).
    """
    by_split = group_windows_by_split(windows)
    counts: Dict[str, int] = {}
    root = Path(output_root)
    for split in splits:
        ws = by_split.get(split) or []
        dir_name = split_to_dir.get(split, split)
        if not ws:
            root.joinpath(dir_name).mkdir(parents=True, exist_ok=True)
            counts[split] = 0
            continue
        frame = windows_to_frame(ws)
        split_dir = root / dir_name
        split_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(split_dir / "sequences.parquet", index=False)
        counts[split] = len(ws)
    return counts