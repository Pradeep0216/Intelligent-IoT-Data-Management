import logging
import math
import time
import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd

import config
from logging_setup import get_logger
from main import detect_correlation_change_alert as run_correlation_pipeline
from main import to_iso8601, with_iso_timestamps
from preprocessing import InputValidationError


app = Flask(__name__)
CORS(app)

logger = get_logger("api")

DEFAULT_WINDOW_SIZE = 20
DEFAULT_STEP_SIZE = 10
DEFAULT_METHOD = "pearson"

DEFAULT_STRONG_CORR_THRESHOLD = 0.7
DEFAULT_WEAK_CORR_THRESHOLD = 0.4
DEFAULT_DELTA_THRESHOLD = 0.3

ALLOWED_CORRELATION_METHODS = {"pearson", "spearman"}


def parse_positive_int(value, name):
    """Convert a request value to a positive integer."""
    try:
        parsed_number = float(value)
    except (TypeError, ValueError):
        raise InputValidationError(
            f"'{name}' must be a positive integer."
        )

    if (
        not math.isfinite(parsed_number)
        or not parsed_number.is_integer()
        or parsed_number <= 0
    ):
        raise InputValidationError(
            f"'{name}' must be a positive integer."
        )

    return int(parsed_number)


def parse_correlation_threshold(value, name):
    """Convert and validate a correlation threshold in [-1, 1]."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise InputValidationError(
            f"'{name}' must be a number between -1 and 1."
        )

    if not math.isfinite(parsed) or parsed < -1 or parsed > 1:
        raise InputValidationError(
            f"'{name}' must be between -1 and 1."
        )

    return parsed


def parse_delta_threshold(value):
    """Convert and validate an absolute correlation change in [0, 2]."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise InputValidationError(
            "'delta_threshold' must be a number between 0 and 2."
        )

    if not math.isfinite(parsed) or parsed < 0 or parsed > 2:
        raise InputValidationError(
            "'delta_threshold' must be between 0 and 2."
        )

    return parsed


def validate_method(method):
    """Accept only correlation methods supported by the API contract."""
    if method not in ALLOWED_CORRELATION_METHODS:
        raise InputValidationError(
            "'method' must be either 'pearson' or 'spearman'."
        )

    return method


def validate_configuration(
    window_size,
    step_size,
    strong_corr_threshold,
    weak_corr_threshold,
    delta_threshold,
):
    """Validate configurable correlation alert parameters."""
    window_size = parse_positive_int(window_size, "window_size")
    step_size = parse_positive_int(step_size, "step_size")
    strong_corr_threshold = parse_correlation_threshold(
        strong_corr_threshold,
        "strong_corr_threshold",
    )
    weak_corr_threshold = parse_correlation_threshold(
        weak_corr_threshold,
        "weak_corr_threshold",
    )
    delta_threshold = parse_delta_threshold(delta_threshold)

    if weak_corr_threshold >= strong_corr_threshold:
        raise InputValidationError(
            "'weak_corr_threshold' must be less than "
            "'strong_corr_threshold'."
        )

    return (
        window_size,
        step_size,
        strong_corr_threshold,
        weak_corr_threshold,
        delta_threshold,
    )


def _run_pipeline_self_test() -> None:
    """Run a small synthetic dataset through the real pipeline."""
    frame = pd.DataFrame({
        "time": range(30),
        "a": [index % 7 for index in range(30)],
        "b": [(index * 3) % 11 for index in range(30)],
    })

    pipeline_logger = logging.getLogger("correlation.preprocessing")
    previous_level = pipeline_logger.level
    pipeline_logger.setLevel(logging.WARNING)
    try:
        run_correlation_pipeline(
            frame,
            "time",
            ["a", "b"],
            10,
            5,
            "pearson",
        )
    finally:
        pipeline_logger.setLevel(previous_level)


def _readiness_checks():
    """Return readiness and the result of each operational check."""
    checks = {}
    ready = True

    try:
        import numpy

        checks["dependencies"] = {
            "ok": True,
            "pandas": pd.__version__,
            "numpy": numpy.__version__,
        }
    except Exception as exc:
        ready = False
        checks["dependencies"] = {
            "ok": False,
            "error": str(exc),
        }

    try:
        _run_pipeline_self_test()
        checks["pipeline"] = {
            "ok": True,
            "detail": "self-test run completed",
        }
    except Exception as exc:
        ready = False
        checks["pipeline"] = {
            "ok": False,
            "error": str(exc),
        }

    return ready, checks


@app.route("/service-status", methods=["GET"])
def service_status():
    started_at = time.perf_counter()
    ready, checks = _readiness_checks()
    check_ms = int((time.perf_counter() - started_at) * 1000)

    body = {
        "status": "running" if ready else "degraded",
        "message": (
            "Correlation Alert Service is running."
            if ready
            else "Correlation Alert Service is running but not ready to serve requests."
        ),
        "service": "correlation-alert-api",
        "live": True,
        "ready": ready,
        "checks": checks,
        "check_duration_ms": check_ms,
        "config": config.as_dict(),
    }

    if ready:
        logger.info("[HEALTH] ready=True check_ms=%d", check_ms)
    else:
        failed = [
            name
            for name, check in checks.items()
            if not check.get("ok")
        ]
        logger.error(
            "[HEALTH] ready=False failed=%s check_ms=%d",
            failed,
            check_ms,
        )

    return jsonify(body), (200 if ready else 503)


@app.route("/detect-correlation-alert", methods=["POST"])
def detect_correlation_alert_api():
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

    try:
        if "file" in request.files:
            source = "file"
            uploaded_file = request.files["file"]
            dataframe = pd.read_csv(uploaded_file)
            dataframe.columns = dataframe.columns.str.strip()

            timestamp_col = request.form.get("timestamp_col")
            selected_streams = request.form.get("selected_streams")
            window_size = request.form.get(
                "window_size",
                DEFAULT_WINDOW_SIZE,
            )
            step_size = request.form.get(
                "step_size",
                DEFAULT_STEP_SIZE,
            )
            method = request.form.get("method", DEFAULT_METHOD)
            strong_corr_threshold = request.form.get(
                "strong_corr_threshold",
                DEFAULT_STRONG_CORR_THRESHOLD,
            )
            weak_corr_threshold = request.form.get(
                "weak_corr_threshold",
                DEFAULT_WEAK_CORR_THRESHOLD,
            )
            delta_threshold = request.form.get(
                "delta_threshold",
                DEFAULT_DELTA_THRESHOLD,
            )
        else:
            source = "json"
            body = request.get_json(silent=True)
            if body is None:
                raise InputValidationError(
                    "Request must contain either a CSV file or a valid JSON body."
                )

            data = body.get("data")
            timestamp_col = body.get("timestamp_col")
            selected_streams = body.get("selected_streams")
            window_size = body.get("window_size", DEFAULT_WINDOW_SIZE)
            step_size = body.get("step_size", DEFAULT_STEP_SIZE)
            method = body.get("method", DEFAULT_METHOD)
            strong_corr_threshold = body.get(
                "strong_corr_threshold",
                DEFAULT_STRONG_CORR_THRESHOLD,
            )
            weak_corr_threshold = body.get(
                "weak_corr_threshold",
                DEFAULT_WEAK_CORR_THRESHOLD,
            )
            delta_threshold = body.get(
                "delta_threshold",
                DEFAULT_DELTA_THRESHOLD,
            )

            if data is None:
                raise InputValidationError(
                    "Missing 'data' in request body."
                )

            dataframe = pd.DataFrame(data)
            dataframe.columns = dataframe.columns.str.strip()

        if timestamp_col is None:
            raise InputValidationError("Missing 'timestamp_col'.")

        if selected_streams is None:
            raise InputValidationError("Missing 'selected_streams'.")

        if isinstance(selected_streams, str):
            selected_streams = [
                column.strip()
                for column in selected_streams.split(",")
                if column.strip()
            ]

        if not selected_streams:
            raise InputValidationError(
                "'selected_streams' must contain at least one stream."
            )

        logger.info(
            "[%s] received source=%s rows_in=%d streams=%s "
            "window_size=%s step_size=%s method=%s",
            request_id,
            source,
            len(dataframe),
            selected_streams,
            window_size,
            step_size,
            method,
        )

        (
            window_size,
            step_size,
            strong_corr_threshold,
            weak_corr_threshold,
            delta_threshold,
        ) = validate_configuration(
            window_size,
            step_size,
            strong_corr_threshold,
            weak_corr_threshold,
            delta_threshold,
        )
        method = validate_method(method)

        result = run_correlation_pipeline(
            df=dataframe,
            timestamp_col=timestamp_col,
            selected_streams=selected_streams,
            window_size=window_size,
            step_size=step_size,
            method=method,
            strong_corr_threshold=strong_corr_threshold,
            weak_corr_threshold=weak_corr_threshold,
            delta_threshold=delta_threshold,
        )

        alerts = result["alerts"]
        changes = result["changes"]
        correlations = []

        for item in result["correlation_results"]:
            correlations.append({
                "window_index": item["window_index"],
                "start_time": to_iso8601(item["start_time"]),
                "end_time": to_iso8601(item["end_time"]),
                "window_size": item["window_size"],
                "correlation_matrix": (
                    item["correlation_matrix"]
                    .round(4)
                    .to_dict()
                ),
            })

        data_quality = result.get("data_quality", {})
        runtime_ms = elapsed_ms()

        logger.info(
            "[%s] completed rows_out=%d windows=%d changes=%d alerts=%d "
            "imputed=%d coerced=%d runtime_ms=%d",
            request_id,
            len(result["processed_data"]),
            len(result["windows"]),
            len(changes),
            len(alerts),
            data_quality.get("missing_imputed", 0),
            data_quality.get("non_numeric_coerced", 0),
            runtime_ms,
        )

        if runtime_ms > config.REQUEST_TIMEOUT_SECONDS * 1000:
            logger.warning(
                "[%s] slow request: runtime_ms=%d exceeded budget of %ds",
                request_id,
                runtime_ms,
                config.REQUEST_TIMEOUT_SECONDS,
            )

        response = {
            "status": "success",
            "request_id": request_id,
            "runtime_ms": runtime_ms,
            "configuration": {
                "window_size": window_size,
                "step_size": step_size,
                "method": method,
                "strong_corr_threshold": strong_corr_threshold,
                "weak_corr_threshold": weak_corr_threshold,
                "delta_threshold": delta_threshold,
            },
            "summary": {
                "processed_rows": len(result["processed_data"]),
                "windows": len(result["windows"]),
                "correlation_results": len(result["correlation_results"]),
                "changes": len(changes),
                "alerts": len(alerts),
                "non_numeric_values_coerced": data_quality.get(
                    "non_numeric_coerced",
                    0,
                ),
                "missing_values_imputed": data_quality.get(
                    "missing_imputed",
                    0,
                ),
            },
            "correlations": correlations,
            "alerts": with_iso_timestamps(alerts),
            "changes": with_iso_timestamps(changes),
        }

        return jsonify(response), 200

    except InputValidationError as exc:
        logger.warning(
            "[%s] invalid_input after %dms: %s",
            request_id,
            elapsed_ms(),
            exc,
        )
        return jsonify({
            "status": "error",
            "error_type": "invalid_input",
            "request_id": request_id,
            "message": str(exc),
        }), 400

    except Exception as exc:
        logger.error(
            "[%s] internal_error after %dms: %s",
            request_id,
            elapsed_ms(),
            exc,
            exc_info=True,
        )
        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "request_id": request_id,
            "message": str(exc),
        }), 500


if __name__ == "__main__":
    logger.info("[STARTUP] Correlation Alert Service starting")
    for key, value in config.as_dict().items():
        logger.info("[STARTUP] %s=%s", key, value)
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )
