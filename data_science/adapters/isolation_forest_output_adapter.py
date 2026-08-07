"""
Isolation Forest standard JSON output adapter.

Converts the output produced by the standard detector runner for
Isolation Forest into the proposed standard Models JSON structure.

Required output fields:
- timestamp
- sensor_id
- alert_type
- method
- anomaly_flag
- score

Optional output fields:
- severity
- message
- supporting_values

Temporary severity logic:
- Normal result -> "normal"
- Detected anomaly -> "high"

The severity logic is temporary and is not calibrated for production use.
"""

from typing import Any

import pandas as pd


REQUIRED_FIELDS = [
    "timestamp",
    "sensor_id",
    "alert_type",
    "method",
    "anomaly_flag",
    "score",
]

OPTIONAL_FIELDS = [
    "severity",
    "message",
    "supporting_values",
]


def _make_json_safe(value: Any) -> Any:
    """Convert common Pandas/NumPy values into JSON-safe Python values."""

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def _format_timestamp(timestamp: Any) -> str:
    """Convert timestamp into an ISO-formatted string where possible."""

    if hasattr(timestamp, "isoformat"):
        return timestamp.isoformat()

    return str(timestamp)


def calculate_severity(anomaly_flag: bool) -> str:
    """
    Apply temporary severity logic.

    Current prototype rule:
    - False -> normal
    - True  -> high

    This is placeholder logic only.
    """

    if not anomaly_flag:
        return "normal"

    return "high"


def adapt_isolation_forest_output(
    detector_output: dict,
    input_df: pd.DataFrame,
    sensor_id: str,
) -> list[dict]:
    """
    Convert Isolation Forest runner output into standard Models JSON records.

    Parameters
    ----------
    detector_output:
        Dictionary returned by the standard detector runner.

    input_df:
        Numerical DataFrame used by the runner. Values from the matching
        timestamp are added to supporting_values.

    sensor_id:
        Identifier for the sensor source or stream.

    Returns
    -------
    list[dict]
        One standard output record for each timestamp.
    """

    # Check whether Pradeep's detector runner completed successfully.
    if detector_output.get("status") != "success":
        raise ValueError(
            detector_output.get(
                "error",
                "Detector runner did not complete successfully.",
            )
        )

    required_detector_fields = {
        "timestamp",
        "model_name",
        "anomaly_flag",
        "score",
    }

    missing_fields = required_detector_fields.difference(detector_output)

    if missing_fields:
        missing_text = ", ".join(sorted(missing_fields))
        raise ValueError(
            f"Detector output is missing required fields: {missing_text}"
        )

    if not isinstance(sensor_id, str) or not sensor_id.strip():
        raise ValueError("sensor_id must be a non-empty string.")

    timestamps = detector_output["timestamp"]
    anomaly_flags = detector_output["anomaly_flag"]
    scores = detector_output["score"]
    method = str(detector_output["model_name"])

    flags_series = pd.Series(
        anomaly_flags,
        index=timestamps,
    ).astype(bool)

    score_series = pd.Series(
        scores,
        index=timestamps,
        dtype=float,
    )

    if len(flags_series) != len(score_series):
        raise ValueError(
            "anomaly_flag and score must contain the same number of results."
        )

    if len(flags_series) != len(input_df):
        raise ValueError(
            "Detector output length does not match the input DataFrame length."
        )

    standard_records = []

    for timestamp in timestamps:

        anomaly_flag = bool(flags_series.loc[timestamp])
        score = float(score_series.loc[timestamp])

        if timestamp not in input_df.index:
            raise ValueError(
                f"Timestamp {timestamp} was not found in the input DataFrame."
            )

        supporting_values = {
            str(column): _make_json_safe(value)
            for column, value
            in input_df.loc[timestamp].to_dict().items()
        }

        if anomaly_flag:
            alert_type = "anomaly"
            message = (
                f"Anomaly detected by {method} "
                f"for sensor {sensor_id}."
            )
        else:
            alert_type = "normal"
            message = (
                f"No anomaly detected by {method} "
                f"for sensor {sensor_id}."
            )

        record = {
            # Required fields
            "timestamp": _format_timestamp(timestamp),
            "sensor_id": sensor_id,
            "alert_type": alert_type,
            "method": method,
            "anomaly_flag": anomaly_flag,
            "score": score,

            # Optional fields
            "severity": calculate_severity(anomaly_flag),
            "message": message,
            "supporting_values": supporting_values,
        }

        standard_records.append(record)

    return standard_records