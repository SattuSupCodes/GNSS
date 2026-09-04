"""Calibrate processed Phase 1 trips via the Phase 2 calibration pipeline.

Reads ``data/processed/trip_<id>.parquet``, applies gravity estimation,
(optional) sensor calibration, orientation estimation and phone alignment, and
writes the enriched frames to ``data/calibrated/trip_<id>.parquet`` together
with serialisable calibration metadata.

Usage:
    python scripts/calibrate_dataset.py
    python scripts/calibrate_dataset.py --trip vw16b
    python scripts/calibrate_dataset.py --fit-accel --fit-mag
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml

from src.calibration.calibration_pipeline import CalibrationConfig, CalibrationPipeline
from src.data.dataset_manager import DatasetManager
from src.data.io_vnbd_loader import IOVNBDDataset


def load_yaml(name: str) -> dict:
    p = REPO_ROOT / "configs" / name
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_config(d: dict, fit_accel: bool, fit_mag: bool) -> CalibrationConfig:
    cal = d.get("calibration", {})
    grav = cal.get("gravity", {})
    orient = cal.get("orientation", {})
    align = cal.get("alignment", {})
    kal = cal.get("calibration", {})
    return CalibrationConfig(
        gravity_method=grav.get("method", "lowpass"),
        gravity_cutoff_hz=float(grav.get("cutoff_hz", 0.05)),
        gravity_filter_order=int(grav.get("filter_order", 4)),
        fs=float(grav.get("fs", 10.0)),
        gravity_min_samples=int(grav.get("min_samples", 20)),
        fusion_gain=float(orient.get("fusion_gain", 0.1)),
        ema_tau_s=float(orient.get("ema_tau_s", 1.0)),
        mag_field_min_ut=float(orient.get("mag_field_min_ut", 20.0)),
        mag_field_max_ut=float(orient.get("mag_field_max_ut", 70.0)),
        alignment_convention=align.get("convention", "TOP_NORTH_SCREEN_UP"),
        alignment_yaw_deg=optim(align.get("yaw_deg")),
        alignment_pitch_deg=optim(align.get("pitch_deg")),
        alignment_roll_deg=optim(align.get("roll_deg")),
        calibrate_accel=bool(kal.get("accel", False)) or fit_accel,
        calibrate_gyro=bool(kal.get("gyro", False))
        or bool(kal.get("estimate_gyro_bias_from_rest", False)),
        calibrate_mag=bool(kal.get("mag", False)) or fit_mag,
        estimate_gyro_bias_from_rest=bool(kal.get("estimate_gyro_bias_from_rest", False)),
    )


def optim(v):
    return None if v is None else float(v)


def find_rest_window(df: pd.DataFrame, fs: float = 10.0, min_seconds: float = 3.0):
    """Return the first contiguous near-rest block (start, stop) row indices, or
    None. Rest = accel magnitude within [9.3, 10.3] AND gyro magnitude small
    AND GNSS speed ~0 when available."""
    n = int(min_seconds * fs)
    if len(df) < n:
        return None
    amag = np.sqrt(
        pd.to_numeric(df["accel_x"], errors="coerce") ** 2
        + pd.to_numeric(df["accel_y"], errors="coerce") ** 2
        + pd.to_numeric(df["accel_z"], errors="coerce") ** 2
    ).to_numpy()
    gmag = np.sqrt(
        pd.to_numeric(df["gyro_x"], errors="coerce") ** 2
        + pd.to_numeric(df["gyro_y"], errors="coerce") ** 2
        + pd.to_numeric(df["gyro_z"], errors="coerce") ** 2
    ).to_numpy()
    a_ok = np.isfinite(amag) & (amag > 9.3) & (amag < 10.3)
    g_ok = np.isfinite(gmag) & (gmag < 0.3)
    rest = a_ok & g_ok
    # rolling sum: need n consecutive True
    for start in range(0, len(rest) - n + 1):
        if rest[start : start + n].all():
            return start, start + n
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trip", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--config", type=str, default="calibration_config.yaml")
    parser.add_argument(
        "--fit-accel",
        action="store_true",
        help="Enable accelerometer bias/scale estimation from the trip stream.",
    )
    parser.add_argument(
        "--fit-mag",
        action="store_true",
        help="Enable magnetometer bias/scale estimation from the trip stream.",
    )
    args = parser.parse_args()

    data_cfg = load_yaml("data_config.yaml")["dataset"]
    raw_root = REPO_ROOT / data_cfg["raw_root"]
    processed_root = REPO_ROOT / data_cfg["processed_root"]
    manager = DatasetManager(str(raw_root), str(processed_root))
    IOVNBDDataset(str(raw_root)).check_smartphone_data_available()

    cfg = build_config(load_yaml(args.config), args.fit_accel, args.fit_mag)
    cal_cfg_y = load_yaml(args.config).get("calibration", {}).get("output", {})
    out_root = REPO_ROOT / cal_cfg_y.get("calibrated_root", "data/calibrated")

    trip_ids = [args.trip] if args.trip else manager.list_trips()
    if args.limit:
        trip_ids = trip_ids[: args.limit]
    if not trip_ids:
        print("No trips to calibrate.")
        return 1

    pipeline = CalibrationPipeline(cfg)
    index: list = []
    out_root.mkdir(parents=True, exist_ok=True)
    for tid in trip_ids:
        try:
            trip = manager.load_processed_trip(tid)
        except FileNotFoundError as exc:
            print(f"SKIP {tid}: {exc}")
            continue
        gyro_rest = None
        if cfg.estimate_gyro_bias_from_rest:
            win = find_rest_window(trip.data)
            if win is None:
                print(f"NOTE {tid}: no rest block -> gyro profile stays configured")
            else:
                s, e = win
                gyro_rest = np.column_stack(
                    [
                        pd.to_numeric(trip.data[c], errors="coerce").to_numpy()[s:e]
                        for c in ("gyro_x", "gyro_y", "gyro_z")
                    ]
                )
        src_file = str(trip.data["source_file"].iloc[0]) if "source_file" in trip.data.columns else None
        result = pipeline.run(trip.data, trip_id=tid, source_file=src_file, gyro_rest_samples=gyro_rest)
        out = result.frame
        out_path = out_root / f"trip_{tid}.parquet"
        out.to_parquet(out_path, index=False)
        index.append(
            {
                "trip_id": tid,
                "rows": int(len(out)),
                "file": str(out_path),
                "status": result.status,
                "gravity_mean": result.metadata["gravity"].get("magnitude_mean"),
                "n_windows_of_100": int(len(out) // 100),
            }
        )
        print(f"OK {tid}: {len(out)} rows, columns+{len(result.added_columns)} -> {out_path.name}")

    meta_file = out_root / cal_cfg_y.get("metadata_file", "calibration_metadata.json")
    meta_file.write_text(
        json.dumps(
            {
                "config": cfg.to_dict(),
                "output_root": str(out_root),
                "trips": index,
                "notes": [
                    "Whole-frame calibration preserves Phase 1 raw columns.",
                    "configured = identity profile (copy-through); estimated = fitted.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {len(index)} calibrated trips. Metadata: {meta_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())