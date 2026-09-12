"""Quick check: run the real AIntl pipeline against the farming dataset.

Confirms the pipeline still behaves as documented in README.md, without
needing the full notebook. Run from the repo root:

    python data_science/datasets/farming/quick_check.py

Expected output: {'processed_items': 7261, 'alert_count': 535}
"""
import sys
from pathlib import Path

import pandas as pd

# Repo root is three levels up from this file (data_science/datasets/farming/quick_check.py).
# Added to sys.path so this runs as a plain script from anywhere, no -m or PYTHONPATH needed.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics_integration.pipeline import run_analytics_pipeline

RENAMES = {
    "field1": "temp_c", "field2": "wet_bulb_c", "field3": "temp2_c",
    "field4": "humidity_pct", "field5": "abs_humidity_gm3",
    "field6": "dew_point_c", "field7": "humidity_deficit_gm3", "field8": "co2_ppm",
}
FAULT_SENTINELS = {99.9, 455.0, 9999.0, 0.0}


def load_clean_data(csv_path=None):
    """Reproduces Task 1/2's preprocessing: field mapping, fault-sentinel
    removal, and selecting the single longest continuous export block."""
    if csv_path is None:
        csv_path = REPO_ROOT / "data_science/datasets/farming/data/farming.csv"
    df = pd.read_csv(csv_path).rename(columns=RENAMES)
    df["timestamp"] = pd.to_datetime(df["created_at"], format="mixed", utc=True)

    fault_mask = df[["temp_c", "humidity_pct", "co2_ppm"]].isin(FAULT_SENTINELS).any(axis=1)
    gaps = df["timestamp"].diff()
    block_id = (gaps > gaps.median() * 100).cumsum()
    main_block = block_id.value_counts().idxmax()

    clean = df[(block_id == main_block) & ~fault_mask].sort_values("timestamp").reset_index(drop=True)
    clean["timestamp"] = clean["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return clean


def main():
    data = load_clean_data()
    print(f"Loaded and cleaned data: {len(data)} rows")

    response = run_analytics_pipeline(
        df=data,
        timestamp_col="timestamp",
        entity_id="greenhouse_ch80502",
        model_metric="temp_c",
        correlation_streams=["temp_c", "humidity_pct"],
        detector_name="isolationforest",
        detector_parameters={"contamination": 0.05},
        correlation_window_size=20,
        correlation_step_size=10,
        correlation_method="pearson",
    )
    print("Pipeline summary:", response["summary"])


if __name__ == "__main__":
    main()
