"""Runs the specific evaluation checks described in the PDF report, as
plain terminal output. This is the same logic that lives inside
notebook.ipynb's cells, pulled out into one standalone, runnable script.

Covers:
  1. Detector alone (Models path)
  2. Correlation alone (two experiments)
  3. Full combined pipeline
  4. Cross-check against independent statistics (percentile outliers)
  5. Determinism check (run twice, compare)
  6. Input validator behaviour on bad data (missing columns, duplicate
     timestamps, NaN values, fault-sentinel values)

Run from anywhere:

    python data_science/datasets/farming/run_checks.py
"""
import numpy as np
import pandas as pd

from quick_check import load_clean_data, REPO_ROOT
import sys
sys.path.insert(0, str(REPO_ROOT))

from data_science.input_validator import validate_input, InputValidationError
from data_science.detector_runner import run_detector
from analytics_integration.pipeline import (
    run_analytics_pipeline,
    run_correlation_path,
)

FAULT_SENTINELS = {99.9, 455.0, 9999.0, 0.0}


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    main_df = load_clean_data()

    # ---------------------------------------------------------------
    section("1. Detector alone (Models path)")
    model_df = main_df.set_index(pd.to_datetime(main_df["timestamp"]))[["temp_c"]]
    validated = validate_input(model_df, min_readings=20)
    result = run_detector("isolationforest", validated[["temp_c"]], parameters={"contamination": 0.05})
    flag = result["anomaly_flag"]
    print(f"Status: {result['status']}")
    print(f"Flagged: {flag.sum()} / {len(flag)} ({flag.mean()*100:.2f}%)")
    print(f"Runtime: {result['runtime']:.4f}s")

    # ---------------------------------------------------------------
    section("2. Correlation alone (two experiments)")
    alerts_a, _ = run_correlation_path(
        df=main_df, timestamp_col="timestamp",
        correlation_streams=["temp_c", "humidity_pct"],
        window_size=20, step_size=10, method="pearson",
    )
    alerts_b, _ = run_correlation_path(
        df=main_df, timestamp_col="timestamp",
        correlation_streams=["temp_c", "co2_ppm"],
        window_size=20, step_size=10, method="pearson",
    )
    print(f"temp_c vs humidity_pct: {len(alerts_a)} alerts")
    print(f"temp_c vs co2_ppm:      {len(alerts_b)} alerts")

    # ---------------------------------------------------------------
    section("3. Full combined pipeline")
    response = run_analytics_pipeline(
        df=main_df, timestamp_col="timestamp", entity_id="greenhouse_ch80502",
        model_metric="temp_c", correlation_streams=["temp_c", "humidity_pct"],
        detector_name="isolationforest", detector_parameters={"contamination": 0.05},
        correlation_window_size=20, correlation_step_size=10, correlation_method="pearson",
    )
    print("Summary:", response["summary"])
    print("Draft V0.1 validation: passed (would have raised otherwise)")

    # ---------------------------------------------------------------
    section("4. Cross-check against independent statistics")
    q_hi = validated["temp_c"].quantile(0.995)
    q_lo = validated["temp_c"].quantile(0.005)
    known_outliers = set(validated.index[(validated["temp_c"] >= q_hi) | (validated["temp_c"] <= q_lo)])
    flagged_idx = set(validated.index[flag])
    overlap = known_outliers & flagged_idx
    print(f"Independently-identified top/bottom 0.5% outliers: {len(known_outliers)}")
    print(f"Also caught by the detector: {len(overlap)} / {len(known_outliers)} "
          f"({len(overlap)/len(known_outliers)*100:.1f}%)")

    # ---------------------------------------------------------------
    section("5. Determinism check (run twice, compare)")
    result2 = run_detector("isolationforest", validated[["temp_c"]], parameters={"contamination": 0.05})
    same = (result["anomaly_flag"] == result2["anomaly_flag"]).all()
    print(f"Same flags both runs? {same}")

    # ---------------------------------------------------------------
    section("6. Input validator behaviour on bad data")

    # 6a. Missing field mapping
    raw_df = pd.read_csv(REPO_ROOT / "data_science/datasets/farming/data/farming.csv")
    raw_df["timestamp"] = pd.to_datetime(raw_df["created_at"], format="mixed", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        run_analytics_pipeline(
            df=raw_df, timestamp_col="timestamp", entity_id="greenhouse_ch80502",
            model_metric="temp_c", correlation_streams=["temp_c", "humidity_pct"],
            detector_name="isolationforest",
        )
        print("6a. Missing field mapping: did NOT raise (unexpected)")
    except ValueError as e:
        print(f"6a. Missing field mapping: correctly rejected -> {e}")

    # 6b. Duplicate timestamps
    dup_df = main_df.copy()
    dup_df.loc[1, "timestamp"] = dup_df.loc[0, "timestamp"]
    try:
        validate_input(dup_df[["timestamp", "temp_c"]], sensor_cols=["temp_c"], min_readings=20)
        print("6b. Duplicate timestamps: did NOT raise (unexpected)")
    except InputValidationError as e:
        print(f"6b. Duplicate timestamps: correctly rejected -> {e}")

    # 6c. NaN sensor value
    nan_df = main_df.copy()
    nan_df.loc[5, "temp_c"] = np.nan
    try:
        validate_input(nan_df[["timestamp", "temp_c"]], sensor_cols=["temp_c"], min_readings=20)
        print("6c. NaN sensor value: did NOT raise (unexpected)")
    except InputValidationError as e:
        print(f"6c. NaN sensor value: correctly rejected -> {e}")

    # 6d. Fault-sentinel value (the known gap)
    sentinel_df = main_df.copy()
    sentinel_df.loc[5, "temp_c"] = 99.9
    validated_with_sentinel = validate_input(
        sentinel_df[["timestamp", "temp_c"]], sensor_cols=["temp_c"], min_readings=20
    )
    print(f"6d. Fault-sentinel value (99.9): accepted without complaint "
          f"({len(validated_with_sentinel)} rows) - this is the known gap.")

    section("Done")


if __name__ == "__main__":
    main()
