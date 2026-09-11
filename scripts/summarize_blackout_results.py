from pathlib import Path
import re
import pandas as pd
import numpy as np


INPUT = Path("models/blackout_speed_predictions.csv")
OUTPUT = Path("models/blackout_duration_summary.csv")


def rmse(actual, predicted):
    return float(np.sqrt(np.mean((predicted - actual) ** 2)))


df = pd.read_csv(INPUT)

required = [
    "scenario_id",
    "trip_id",
    "timestamp",
    "blackout_phase",
    "gnss_available",
    "reference_speed_kmh",
    "predicted_speed_kmh",
]

missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns: {missing}")


# Keep only samples where offline ground truth exists
df = df.dropna(
    subset=["reference_speed_kmh", "predicted_speed_kmh"]
).copy()


# Extract blackout duration from scenario_id.
# Example:
# t4__blk10s_00 -> 10
def extract_duration(s):
    match = re.search(r"blk(\d+)s", str(s).lower())
    return int(match.group(1)) if match else np.nan


df["blackout_duration_s"] = df["scenario_id"].apply(extract_duration)

if df["blackout_duration_s"].isna().any():
    bad = df.loc[
        df["blackout_duration_s"].isna(),
        "scenario_id"
    ].unique()[:10]
    print("WARNING: Could not extract duration from:")
    print(bad)


df["error"] = (
    df["predicted_speed_kmh"] -
    df["reference_speed_kmh"]
)

df["abs_error"] = df["error"].abs()
df["squared_error"] = df["error"] ** 2


summary = (
    df.dropna(subset=["blackout_duration_s"])
    .groupby("blackout_duration_s")
    .agg(
        samples=("error", "size"),
        scenarios=("scenario_id", "nunique"),
        mae=("abs_error", "mean"),
        rmse=("squared_error", lambda x: np.sqrt(x.mean())),
        mean_reference_speed=("reference_speed_kmh", "mean"),
        mean_predicted_speed=("predicted_speed_kmh", "mean"),
    )
    .reset_index()
    .sort_values("blackout_duration_s")
)


summary.to_csv(OUTPUT, index=False)


print()
print("=" * 75)
print("BLACKOUT PERFORMANCE BY DURATION")
print("=" * 75)

print(
    summary.to_string(
        index=False,
        formatters={
            "mae": "{:.4f}".format,
            "rmse": "{:.4f}".format,
            "mean_reference_speed": "{:.2f}".format,
            "mean_predicted_speed": "{:.2f}".format,
        },
    )
)

print()
print(f"Saved -> {OUTPUT}")