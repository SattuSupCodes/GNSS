"""Cross-source synchronization: smartphone IMU vs vehicle CAN reference.

For a given trip id this script:
    1. Loads the smartphone frame (S-*.csv) and, when present, the matching
       vehicle reference frame (V-*.csv).
    2. Estimates a constant time offset between the two via trajectory
       cross-correlation (``estimate_constant_offset``).
    3. Aligns the vehicle reference onto the smartphone grid.
    4. Saves the smartphone frame (with GNSS forward-filled) and the vehicle
       reference frame (tagged ``is_reference=True``) as Parquet files under
       ``data/processed/synchronized``.

Vehicle data is REFERENCE ONLY (used for offline evaluation of dead reckoning),
and is never merged into the smartphone runtime frame.

Usage:
    python scripts/synchronize_data.py --trip vw16b
    python scripts/synchronize_data.py --trip vw16b --offset -0.3   # force offset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.data.dataset_manager import DatasetManager
from src.data.io_vnbd_loader import (
    IOVNBDDataset,
    load_smartphone_trip,
    load_vehicle_csv,
)
from src.preprocessing.synchronization import (
    estimate_constant_offset,
    ffill_gnss,
    synchronize_vehicle_to_grid,
)

SYNC_OUT = REPO_ROOT / "data" / "processed" / "synchronized"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trip", required=True, help="Trip id (e.g. vw16b).")
    parser.add_argument(
        "--offset",
        type=float,
        default=None,
        help="Manually force the constant offset in seconds.",
    )
    parser.add_argument(
        "--raw", type=str, default="data/raw", help="Raw data root."
    )
    args = parser.parse_args()

    ds = IOVNBDDataset(str(REPO_ROOT / args.raw))
    s_path = ds.smartphone_file_for_trip(args.trip)
    if s_path is None:
        print(f"No smartphone file for trip '{args.trip}'.")
        return 1
    v_path = ds.vehicle_file_for_trip(args.trip)

    s_df, s_meta = load_smartphone_trip(ds, args.trip)

    if args.offset is None and v_path is not None:
        v_df = _abs_time_from_seconds_of_day(
            load_vehicle_csv(v_path, trip_id=args.trip), s_df
        )
        offset = estimate_constant_offset(
            s_df,
            v_df,
            a_trace_col="gps_heading_deg",
            b_trace_col="Heading (degrees)",
            max_lag_seconds=5.0,
            resolution=0.1,
        )
        print(
            f"Estimated offset r = {offset:+.3f} s "
            "(add to vehicle timestamps to align them with the smartphone)"
        )
    else:
        v_df = None
        offset = args.offset if args.offset is not None else 0.0

    # Smartphone stays on its native clock; only GNSS is forward-filled so every
    # IMU row carries the best known fix.
    s_aligned = ffill_gnss(s_df.copy())

    out_dir = SYNC_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    s_out = out_dir / f"trip_{args.trip}_smartphone.parquet"
    s_aligned.to_parquet(s_out, index=False)
    print(f"Wrote smartphone: {s_out}")

    if v_path is not None:
        if v_df is None:
            v_df = _abs_time_from_seconds_of_day(
                load_vehicle_csv(v_path, trip_id=args.trip), s_df
            )
        # Align the vehicle reference onto the smartphone clock using +offset.
        grid = (
            pd.to_numeric(s_aligned["timestamp"], errors="coerce").to_numpy()
            + offset
        )
        v_ref = synchronize_vehicle_to_grid(v_df, grid)
        v_out = out_dir / f"trip_{args.trip}_vehicle_reference.parquet"
        v_ref.to_parquet(v_out, index=False)
        print(f"Wrote reference : {v_out}")

    print("Done.")
    return 0


def _abs_time_from_seconds_of_day(v_df: pd.DataFrame, s_df: pd.DataFrame) -> pd.DataFrame:
    """Convert vehicle 'Time Since Start of Day (seconds)' to local absolute
    epoch seconds using the smartphone recording's local date (both streams are
    local wall-clock on the same recording day)."""
    from src.data.data_schema import normalize_source_column

    out = v_df.copy()
    sod_col = next(
        (
            c
            for c in out.columns
            if normalize_source_column(c) == "TIME SINCE START OF DAY (SECONDS)"
        ),
        None,
    )
    if sod_col is None:
        return out
    s_ts = pd.to_numeric(s_df["timestamp"], errors="coerce").dropna()
    if not len(s_ts):
        return out
    local_midnight = pd.Timestamp(float(s_ts.min()), unit="s").normalize()
    midnight_epoch = local_midnight.timestamp()
    sod = pd.to_numeric(out[sod_col], errors="coerce")
    out["timestamp"] = midnight_epoch + sod
    return out


if __name__ == "__main__":
    sys.exit(main())