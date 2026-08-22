import pandas as pd
import pytest

from anomaly_injector import inject_point_spikes
from input_validator import validate_input, InputValidationError
from detector_runner import run_detector
from evaluator import evaluate
from report_output import generate_benchmark_report


def _through_pipeline(df, detector_name="isolationforest", parameters=None, **validate_kwargs):
    """validator -> runner, wired together exactly as a real caller would."""
    clean = validate_input(df, **validate_kwargs)
    result = run_detector(detector_name, clean, parameters=parameters)
    return clean, result


# ---------------------------------------------------------------------------
# 1. Normal detection
# ---------------------------------------------------------------------------

def test_normal_detection_end_to_end(normal_df, tmp_path):
    clean, result = _through_pipeline(normal_df, parameters={"contamination": 0.05})

    assert result["status"] == "success"
    assert result["model_name"] == "IsolationForest"
    assert len(result["anomaly_flag"]) == len(clean)

    flagged = int(result["anomaly_flag"].sum())
    assert 0 < flagged <= int(0.05 * len(clean)) + 2  # bounded by the contamination setting

    labels = pd.Series(False, index=clean.index)
    eval_row = evaluate(result, labels)
    eval_row["detector"] = result["model_name"]
    assert eval_row["n_actual"] == 0

    out_dir = tmp_path / "normal_report"
    generate_benchmark_report(
        pd.DataFrame([eval_row]), {result["model_name"]: result}, labels, output_dir=str(out_dir)
    )
    assert (out_dir / "benchmark_report_summary.txt").exists()


# ---------------------------------------------------------------------------
# 2. Anomaly detection
# ---------------------------------------------------------------------------

def test_anomaly_detection_end_to_end(normal_df, tmp_path):
    injected_df, injector_labels = inject_point_spikes(
        normal_df, n_anomalies=10, magnitude=6.0, random_seed=7
    )
    labels = injector_labels != "normal"  # bool Series, True = anomaly

    clean, result = _through_pipeline(injected_df, parameters={"contamination": 0.05})
    assert result["status"] == "success"

    eval_row = evaluate(result, labels)
    eval_row["detector"] = result["model_name"]
    assert eval_row["n_actual"] == 10
    assert eval_row["recall"] >= 0.7  # large, well-separated spikes should mostly be caught

    out_dir = tmp_path / "anomaly_report"
    generate_benchmark_report(
        pd.DataFrame([eval_row]), {result["model_name"]: result}, labels, output_dir=str(out_dir)
    )
    assert (out_dir / "benchmark_report_summary.txt").exists()
    assert (out_dir / "confusion_summary.png").exists()


# ---------------------------------------------------------------------------
# 3. Failure: empty data
# ---------------------------------------------------------------------------

def test_empty_data_rejected_before_runner(empty_df):
    with pytest.raises(InputValidationError, match="empty"):
        validate_input(empty_df)


# ---------------------------------------------------------------------------
# 4. Failure: bad timestamps
# ---------------------------------------------------------------------------

def test_unparseable_timestamp_rejected(df_unparseable_timestamp):
    with pytest.raises(InputValidationError, match="could not be parsed as datetime"):
        validate_input(df_unparseable_timestamp)


def test_implausible_numeric_timestamp_rejected(df_implausible_numeric_timestamp):
    with pytest.raises(InputValidationError, match="implausible"):
        validate_input(df_implausible_numeric_timestamp)


def test_implausible_numeric_timestamp_accepted_when_acknowledged(df_implausible_numeric_timestamp):
    result = validate_input(df_implausible_numeric_timestamp, timestamp_is_index=True)
    assert len(result) == 4


def test_duplicate_timestamps_rejected(df_duplicate_timestamps):
    with pytest.raises(InputValidationError, match="Duplicate timestamps"):
        validate_input(df_duplicate_timestamps)


# ---------------------------------------------------------------------------
# 5. Failure: unknown detector name
# ---------------------------------------------------------------------------

def test_unknown_detector_name_returns_graceful_failure(normal_df):
    clean, result = _through_pipeline(normal_df, detector_name="totally_unknown_model")
    assert result["status"] == "failed"
    assert "not supported" in result["error"]


def test_unknown_detector_name_lookup_is_case_insensitive(normal_df):
    clean, result = _through_pipeline(normal_df, detector_name="IsolationForest")
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# 6. Failure: incomplete detector output
# ---------------------------------------------------------------------------

def test_runner_catches_detector_output_missing_required_key(normal_df, monkeypatch):
    import detector_runner

    class BrokenDetector:
        def __init__(self, **_kwargs):
            pass

        def detect(self, df):
            return {"model_name": "BrokenDetector", "runtime": 0.001}  # no anomaly_flag

    monkeypatch.setattr(detector_runner, "IsolationForestDetector", BrokenDetector)
    clean = validate_input(normal_df)
    result = detector_runner.run_detector("isolationforest", clean)

    assert result["status"] == "failed"
    assert "error" in result


def test_runner_catches_detector_output_that_is_not_a_dict(normal_df, monkeypatch):
    import detector_runner

    class NotADictDetector:
        def __init__(self, **_kwargs):
            pass

        def detect(self, df):
            return [True, False, True]

    monkeypatch.setattr(detector_runner, "IsolationForestDetector", NotADictDetector)
    clean = validate_input(normal_df)
    result = detector_runner.run_detector("isolationforest", clean)

    assert result["status"] == "failed"


def test_evaluator_rejects_output_missing_anomaly_flag():
    labels = pd.Series([False, True, False])
    with pytest.raises(ValueError, match="anomaly_flag"):
        evaluate({"model_name": "X"}, labels)


def test_evaluator_rejects_output_missing_model_name():
    labels = pd.Series([False, True, False])
    with pytest.raises(ValueError, match="model_name"):
        evaluate({"anomaly_flag": pd.Series([False, True, False])}, labels)


def test_report_output_handles_missing_optional_fields_without_crashing(tmp_path):
    eval_df = pd.DataFrame([{"detector": "StubGood"}])
    results = {"StubGood": {"model_name": "StubGood"}}
    out_dir = tmp_path / "report_out"

    generate_benchmark_report(eval_df, results, labels=None, output_dir=str(out_dir))

    assert (out_dir / "benchmark_report_summary.txt").exists()
