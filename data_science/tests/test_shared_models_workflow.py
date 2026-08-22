import sys

import pandas as pd
import pytest

from input_validator import validate_input, InputValidationError
from evaluator import evaluate
from report_output import generate_benchmark_report


# ---------------------------------------------------------------------------
# 1. Valid sensor data
# ---------------------------------------------------------------------------

def test_valid_sensor_data_is_accepted_and_indexed_by_timestamp(valid_df):
    result = validate_input(valid_df)

    assert not result.empty
    assert result.index.name == "timestamp"
    assert list(result.index) == sorted(result.index)
    assert set(result.columns) == {"s1", "s2"}


def test_valid_sensor_data_end_to_end_through_runner_and_adapter(
    valid_df, detector_runner_module, tmp_path
):
    """validator -> runner -> evaluator -> report_output, using the real modules."""
    clean_df = validate_input(valid_df)

    result = detector_runner_module.run_detector(
        "isolationforest", clean_df, parameters={"contamination": 0.05}
    )
    assert result["status"] == "success"
    assert result["model_name"] == "IsolationForest"

    labels = pd.Series([False] * len(clean_df), index=clean_df.index)
    eval_row = evaluate(result, labels)
    eval_row["detector"] = result["model_name"]
    eval_df = pd.DataFrame([eval_row])

    out_dir = tmp_path / "out"
    generate_benchmark_report(
        eval_df, {result["model_name"]: result}, labels, output_dir=str(out_dir)
    )
    assert (out_dir / "benchmark_report_summary.txt").exists()


# ---------------------------------------------------------------------------
# 2. Empty dataset
# ---------------------------------------------------------------------------

def test_empty_dataset_rejected(empty_df):
    with pytest.raises(InputValidationError, match="empty"):
        validate_input(empty_df)


# ---------------------------------------------------------------------------
# 3. Missing timestamp column
# ---------------------------------------------------------------------------

def test_missing_timestamp_column_rejected(df_missing_timestamp_col):
    with pytest.raises(InputValidationError, match="timestamp"):
        validate_input(df_missing_timestamp_col)


def test_missing_timestamp_column_accepted_with_custom_column_name(df_missing_timestamp_col):
    df = df_missing_timestamp_col.copy()
    df["time"] = pd.date_range("2024-01-01", periods=len(df), freq="s").astype(str)
    result = validate_input(df, timestamp_col="time")
    assert result.index.name == "time"


# ---------------------------------------------------------------------------
# 4. Missing sensor values (NaN)
# ---------------------------------------------------------------------------

def test_missing_sensor_values_rejected(df_missing_sensor_values):
    with pytest.raises(InputValidationError, match=r"Missing \(NaN\)"):
        validate_input(df_missing_sensor_values)


# ---------------------------------------------------------------------------
# 5. Non-numeric sensor data
# ---------------------------------------------------------------------------

def test_non_numeric_sensor_data_rejected(df_non_numeric_sensor):
    with pytest.raises(InputValidationError, match="not numeric"):
        validate_input(df_non_numeric_sensor)


# ---------------------------------------------------------------------------
# 6. Duplicate timestamps
# ---------------------------------------------------------------------------

def test_duplicate_timestamps_rejected(df_duplicate_timestamps):
    with pytest.raises(InputValidationError, match="Duplicate timestamps"):
        validate_input(df_duplicate_timestamps)


# ---------------------------------------------------------------------------
# 7. Unknown detector name
# ---------------------------------------------------------------------------

def test_detector_runner_import_currently_broken():
    sys.modules.pop("detector_runner", None)
    sys.modules.pop("detectors.isolation_forest_detector", None)
    with pytest.raises(ModuleNotFoundError, match="isolation_forest_detector"):
        import detector_runner  # noqa: F401


def test_unknown_detector_name_returns_graceful_failure(detector_runner_module, valid_df):
    clean_df = validate_input(valid_df)
    result = detector_runner_module.run_detector("totally_unknown_model", clean_df)

    assert result["status"] == "failed"
    assert "not supported" in result["error"]


def test_unknown_detector_name_lookup_is_case_insensitive(detector_runner_module, valid_df):
    clean_df = validate_input(valid_df)
    result = detector_runner_module.run_detector("IsolationForest", clean_df)
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# 8. Detector output missing required fields
# ---------------------------------------------------------------------------

def test_evaluator_rejects_output_missing_anomaly_flag():
    labels = pd.Series([False, True, False])
    with pytest.raises(ValueError, match="anomaly_flag"):
        evaluate({"model_name": "X"}, labels)


def test_evaluator_rejects_output_missing_model_name():
    labels = pd.Series([False, True, False])
    with pytest.raises(ValueError, match="model_name"):
        evaluate({"anomaly_flag": pd.Series([False, True, False])}, labels)


def test_runner_catches_detector_that_returns_incomplete_dict(
    detector_runner_module, valid_df, monkeypatch
):
    clean_df = validate_input(valid_df)

    class BrokenDetector:
        def __init__(self, **_kwargs):
            pass

        def detect(self, df):
            return {"model_name": "BrokenDetector", "runtime": 0.001}  # no anomaly_flag

    monkeypatch.setattr(detector_runner_module, "IsolationForestDetector", BrokenDetector)
    result = detector_runner_module.run_detector("isolationforest", clean_df)

    assert result["status"] == "failed"
    assert "error" in result


def test_runner_catches_detector_output_that_is_not_a_dict(
    detector_runner_module, valid_df, monkeypatch
):
    clean_df = validate_input(valid_df)

    class NotADictDetector:
        def __init__(self, **_kwargs):
            pass

        def detect(self, df):
            return [True, False, True]

    monkeypatch.setattr(detector_runner_module, "IsolationForestDetector", NotADictDetector)
    result = detector_runner_module.run_detector("isolationforest", clean_df)

    assert result["status"] == "failed"


def test_report_output_handles_missing_optional_fields_without_crashing(tmp_path):
    eval_df = pd.DataFrame([{"detector": "StubGood"}])  # no metric columns
    results = {"StubGood": {"model_name": "StubGood"}}  # no anomaly_flag/runtime/score
    out_dir = tmp_path / "report_out"

    generate_benchmark_report(eval_df, results, labels=None, output_dir=str(out_dir))

    assert (out_dir / "benchmark_report_summary.txt").exists()
