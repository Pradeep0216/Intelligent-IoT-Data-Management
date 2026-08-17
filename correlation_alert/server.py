import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from .correlation import (
    DEFAULT_DELTA_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    DEFAULT_METHOD,
    DEFAULT_STEP_SIZE,
    DEFAULT_STRONG_THRESHOLD,
    DEFAULT_WEAK_THRESHOLD,
    DEFAULT_WINDOW_SIZE,
)
from .main import detect_correlation_change_alert
from .preprocessing import InputValidationError
from .serialization import serialize_correlation_results, with_iso_timestamps


def _parse_integer(value, name):
    if isinstance(value, bool):
        raise InputValidationError(f"{name} must be an integer")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"{name} must be an integer") from exc
    if not numeric.is_integer():
        raise InputValidationError(f"{name} must be an integer")
    return int(numeric)


def _parse_float(value, name):
    if isinstance(value, bool):
        raise InputValidationError(f"{name} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"{name} must be numeric") from exc


def _parse_frequency(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return int(numeric) if numeric.is_integer() else numeric


def _parse_selected_streams(value):
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, (list, tuple)):
        raise InputValidationError("selected_streams must be a list or comma separated string")
    return list(value)


def parse_request_input():
    """Read JSON or multipart data and return typed pipeline arguments."""
    if "file" in request.files:
        source = request.form
        df = pd.read_csv(request.files["file"])
    else:
        source = request.get_json(silent=True)
        if not isinstance(source, dict):
            raise InputValidationError("Request body must be a JSON object")
        data = source.get("data")
        if data is None:
            raise InputValidationError("Missing 'data' in request body")
        df = pd.DataFrame(data)

    df.columns = df.columns.str.strip()
    timestamp_col = source.get("timestamp_col")
    selected_streams = source.get("selected_streams")
    if not timestamp_col:
        raise InputValidationError("Missing 'timestamp_col'")
    if selected_streams is None:
        raise InputValidationError("Missing 'selected_streams'")

    return {
        "df": df,
        "timestamp_col": timestamp_col,
        "selected_streams": _parse_selected_streams(selected_streams),
        "window_size": _parse_integer(source.get("window_size", DEFAULT_WINDOW_SIZE), "window_size"),
        "step_size": _parse_integer(source.get("step_size", DEFAULT_STEP_SIZE), "step_size"),
        "method": str(source.get("method", DEFAULT_METHOD)).lower(),
        "strong_corr_threshold": _parse_float(
            source.get("strong_corr_threshold", DEFAULT_STRONG_THRESHOLD),
            "strong_corr_threshold",
        ),
        "weak_corr_threshold": _parse_float(
            source.get("weak_corr_threshold", DEFAULT_WEAK_THRESHOLD),
            "weak_corr_threshold",
        ),
        "delta_threshold": _parse_float(
            source.get("delta_threshold", DEFAULT_DELTA_THRESHOLD),
            "delta_threshold",
        ),
        "medium_threshold": _parse_float(
            source.get("medium_threshold", DEFAULT_MEDIUM_THRESHOLD),
            "medium_threshold",
        ),
        "high_threshold": _parse_float(
            source.get("high_threshold", DEFAULT_HIGH_THRESHOLD),
            "high_threshold",
        ),
        "sampling_frequency": _parse_frequency(source.get("sampling_frequency")),
        "missing_method": source.get("missing_method", "interpolate"),
        "iqr_factor": _parse_float(source.get("iqr_factor", 3.0), "iqr_factor"),
    }


def build_api_response(result):
    """Build the stable JSON response from pipeline output."""
    data_quality = result.get("data_quality", {})
    return {
        "status": "success",
        "summary": {
            "processed_rows": len(result["processed_data"]),
            "windows": len(result["windows"]),
            "correlation_results": len(result["correlation_results"]),
            "changes": len(result["changes"]),
            "alerts": len(result["alerts"]),
            "skipped_pairs": len(result["skipped_pairs"]),
            "non_numeric_values_coerced": data_quality.get("non_numeric_coerced", 0),
            "missing_values_imputed": data_quality.get("missing_imputed", 0),
        },
        "data_quality": data_quality,
        "correlations": serialize_correlation_results(result["correlation_results"]),
        "alerts": with_iso_timestamps(result["alerts"]),
        "changes": with_iso_timestamps(result["changes"]),
        "skipped_pairs": with_iso_timestamps(result["skipped_pairs"]),
    }


def create_app():
    """Create the Flask application for the correlation alert service."""
    app = Flask(__name__)
    CORS(app)

    @app.get("/service-status")
    def service_status():
        return jsonify(
            {
                "status": "running",
                "message": "Correlation Alert Service is running.",
                "service": "correlation-alert-api",
            }
        )

    @app.post("/detect-correlation-alert")
    def detect_correlation_alert_api():
        try:
            result = detect_correlation_change_alert(**parse_request_input())
            return jsonify(build_api_response(result)), 200
        except InputValidationError as exc:
            return (
                jsonify(
                    {
                        "status": "error",
                        "error_type": "invalid_input",
                        "message": str(exc),
                    }
                ),
                400,
            )
        except Exception as exc:
            return (
                jsonify(
                    {
                        "status": "error",
                        "error_type": "internal_error",
                        "message": str(exc),
                    }
                ),
                500,
            )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False, port=5001)
