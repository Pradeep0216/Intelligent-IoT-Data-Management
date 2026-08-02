import pytest

from data_science.adapters.models_output_adapter import adapt_models_output


def test_adapt_normal_models_output():
    model_result = {
        "timestamp": "2026-07-29T10:30:00Z",
        "detector": "IsolationForest",
        "is_anomaly": False,
        "anomaly_score": 0.18,
        "runtime_ms": 21,
        "threshold": 0.7,
    }

    result = adapt_models_output(model_result)

    assert result["timestamp"] == "2026-07-29T10:30:00Z"
    assert result["alert_type"] == "anomaly"
    assert result["method"] == "IsolationForest"
    assert result["is_anomaly"] is False
    assert result["score"] == 0.18
    assert result["target"]["sensor_id"] is None


def test_adapt_anomaly_models_output():
    model_result = {
        "timestamp": "2026-07-29T10:35:00Z",
        "detector": "IsolationForest",
        "is_anomaly": True,
        "anomaly_score": 0.91,
        "runtime_ms": 24,
        "threshold": 0.7,
    }

    result = adapt_models_output(model_result)

    assert result["is_anomaly"] is True
    assert result["score"] == 0.91
    assert result["supporting_values"]["threshold"] == 0.7


def test_missing_required_field():
    model_result = {
        "timestamp": "2026-07-29T10:35:00Z",
        "detector": "IsolationForest",
        "is_anomaly": True,
    }

    with pytest.raises(ValueError):
        adapt_models_output(model_result)


def test_invalid_input_type():
    with pytest.raises(TypeError):
        adapt_models_output(["wrong input"])