"""Adapter for converting Models detector output into shared Analytics format."""

from typing import Any


def adapt_models_output(model_result: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Models output into the shared Analytics alert structure.
    """

    if not isinstance(model_result, dict):
        raise TypeError("model_result must be a dictionary.")

    required_fields = [
        "timestamp",
        "detector",
        "is_anomaly",
        "anomaly_score",
    ]

    missing_fields = [
        field for field in required_fields
        if field not in model_result
    ]

    if missing_fields:
        raise ValueError(
            f"Models output is missing required fields: {', '.join(missing_fields)}"
        )

    return {
        "timestamp": model_result["timestamp"],
        "alert_type": "anomaly",
        "target": {
            "sensor_id": model_result.get("sensor_id")
        },
        "method": model_result["detector"],
        "is_anomaly": model_result["is_anomaly"],
        "score": model_result["anomaly_score"],
        "severity": model_result.get("severity"),
        "message": model_result.get("message"),
        "supporting_values": {
            "runtime_ms": model_result.get("runtime_ms"),
            "threshold": model_result.get("threshold"),
        },
    }