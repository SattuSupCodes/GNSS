"""Blackout validation: baseline engine vs ML-augmented engine (D-T3/D-T4/D-T5).

Method (honest, no vehicle-reference leakage):

    1. For every blackout scenario in ``data/blackout``, run the same engine
       TWICE through ``engine_trip_runner.run_trip``:
         * baseline  -- no ML inference hook
         * ML        -- ``TrainedMLInference`` (D-T3/D-T4/D-T5 artifacts)
    2. The **clean run** of the *original* calibrated trip (GNSS never masked)
       is used as the pseudo-reference trajectory: sensor-identical, so the
       only difference during the outage is the presence/absence of the outage
       itself.  Both runners initialize on the same first GNSS fix, so the ENU
       origins coincide.
    3. During blackout rows we measure estimated-vs-clean error (outage-induced
       divergence), mean predicted confidence/error, and the recovery jump.

Output: per-scenario rows + a summary DataFrame + a small report.
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

from src.engine.engine_trip_runner import run_trip
from src.navigation.engine.model_interface import TrainedMLInference


def scenario_trip(scenario_id: str) -> str:
    return scenario_id.split("__blk")[0]


def clean_trajectory(trip_id: str, config: dict) -> pd.DataFrame:
    path = REPO_ROOT / "data" / "calibrated" / f"trip_{trip_id.lower()}.parquet"
    df = pd.read_parquet(path)
    return run_trip(df, config).trajectory


def during_blackout_error(est: pd.DataFrame, clean: pd.DataFrame) -> dict:
    est = est[["timestamp", "east_m", "north_m", "confidence", "position_error", "blackout_phase"]]
    merged = est.merge(
        clean[["timestamp", "east_m", "north_m"]],
        on="timestamp",
        suffixes=("_est", "_clean"),
    )
    if merged.empty:
        return {}

    out = merged[merged["blackout_phase"].isin(["blackout", "inter_blackout"])]
    if out.empty:
        return {
            "n_blackout_rows": 0,
            "blackout_rmse_m": float("nan"),
            "blackout_mean_error_m": float("nan"),
            "blackout_max_error_m": float("nan"),
            "mean_confidence_blackout": float(merged["confidence"].mean()),
        }

    err = np.hypot(
        out["east_m_est"] - out["east_m_clean"],
        out["north_m_est"] - out["north_m_clean"],
    ).to_numpy(dtype=float)
    err = err[np.isfinite(err)]

    recovery_err = float(np.hypot(
        est["east_m"].iloc[-1] - clean["east_m"].iloc[-1],
        est["north_m"].iloc[-1] - clean["north_m"].iloc[-1],
    ))

    return {
        "n_blackout_rows": int(len(out)),
        "blackout_rmse_m": float(np.sqrt(np.mean(err**2))) if len(err) else float("nan"),
        "blackout_mean_error_m": float(np.mean(err)) if len(err) else float("nan"),
        "blackout_max_error_m": float(np.max(err)) if len(err) else float("nan"),
        "mean_confidence_blackout": float(out["confidence"].mean()),
        "mean_predicted_error_blackout_m": float(out["position_error"].mean()),
        "final_error_after_recovery_m": recovery_err,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=str, default="data/blackout")
    parser.add_argument("--limit-scenarios", type=int, default=None)
    parser.add_argument("--json", type=str, default="models/blackout_ml_validation.json")
    args = parser.parse_args()

    root = REPO_ROOT / args.root
    scenarios = []
    index_path = root / "scenarios_index.json"
    if index_path.exists():
        scenarios = json.loads(index_path.read_text(encoding="utf-8"))
    if not scenarios:
        scenarios = [
            {"scenario_id": p.stem, "file": str(p.relative_to(REPO_ROOT))}
            for p in sorted(root.rglob("*.parquet"))
        ]
    if args.limit_scenarios:
        scenarios = scenarios[: args.limit_scenarios]

    config = {}
    ml_inference = TrainedMLInference()

    rows = []
    for entry in scenarios:
        scenario_id = entry["scenario_id"]
        frame = pd.read_parquet(REPO_ROOT / entry["file"])
        trip_id = scenario_trip(scenario_id)
        duration_s = None
        for part in scenario_id.split("_"):
            if part.endswith("s") and part[:-1].isdigit():
                duration_s = float(part[:-1])

        try:
            clean = clean_trajectory(trip_id, config)
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {scenario_id}: clean-run failed ({exc})")
            continue

        try:
            base = run_trip(frame, config).trajectory
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {scenario_id}: baseline run failed ({exc})")
            continue
        try:
            ml = run_trip(frame, config, ml_inference=ml_inference).trajectory
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {scenario_id}: ML run failed ({exc})")
            continue

        base_metrics = during_blackout_error(base, clean)
        ml_metrics = during_blackout_error(ml, clean)

        rows.append(
            {
                "scenario_id": scenario_id,
                "trip": trip_id,
                "duration_s": duration_s,
                "baseline_rmse_m": base_metrics.get("blackout_rmse_m"),
                "ml_rmse_m": ml_metrics.get("blackout_rmse_m"),
                "baseline_mean_err_m": base_metrics.get("blackout_mean_error_m"),
                "ml_mean_err_m": ml_metrics.get("blackout_mean_error_m"),
                "baseline_max_err_m": base_metrics.get("blackout_max_error_m"),
                "ml_max_err_m": ml_metrics.get("blackout_max_error_m"),
                "baseline_conf_blackout": base_metrics.get("mean_confidence_blackout"),
                "ml_conf_blackout": ml_metrics.get("mean_confidence_blackout"),
                "ml_pred_err_blackout_m": ml_metrics.get("mean_predicted_error_blackout_m"),
                "baseline_final_err_m": base_metrics.get("final_error_after_recovery_m"),
                "ml_final_err_m": ml_metrics.get("final_error_after_recovery_m"),
                "n_blackout_rows": base_metrics.get("n_blackout_rows", 0),
            }
        )
        print(
            f"{scenario_id}: baseRMSE={rows[-1]['baseline_rmse_m']:.2f}m "
            f"mlRMSE={rows[-1]['ml_rmse_m']:.2f}m "
            f"(rows={rows[-1]['n_blackout_rows']})"
        )

    report = pd.DataFrame(rows)

    def _aggr(col):
        v = pd.to_numeric(report[col], errors="coerce").dropna()
        return float(v.mean()) if len(v) else float("nan")

    aggregates = {
        "n_scenarios": len(report),
        "mean_baseline_rmse_m": _aggr("baseline_rmse_m"),
        "mean_ml_rmse_m": _aggr("ml_rmse_m"),
        "mean_baseline_max_err_m": _aggr("baseline_max_err_m"),
        "mean_ml_max_err_m": _aggr("ml_max_err_m"),
        "mean_baseline_final_err_m": _aggr("baseline_final_err_m"),
        "mean_ml_final_err_m": _aggr("ml_final_err_m"),
        "mean_baseline_confidence_blackout": _aggr("baseline_conf_blackout"),
        "mean_ml_confidence_blackout": _aggr("ml_conf_blackout"),
        "mean_ml_predicted_error_blackout_m": _aggr("ml_pred_err_blackout_m"),
    }

    out = {"aggregates": aggregates, "scenarios": report.to_dict(orient="records")}
    out_path = REPO_ROOT / args.json
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nAggregates (mean over scenarios):")
    for k, v in aggregates.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"\nSaved report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())