import logging
import time
import uuid

from flask import Flask, request, jsonify
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


def _run_pipeline_self_test() -> None:
    """Push a tiny synthetic dataset through the real pipeline.

    Liveness only proves the process answered. This proves the thing the service
    exists to do still executes, which is the difference between a green light
    and a useful green light. Kept small so the check stays fast.
    """
    frame = pd.DataFrame({
        "time": range(30),
        "a": [i % 7 for i in range(30)],
        "b": [(i * 3) % 11 for i in range(30)],
    })

    # Quieten the pipeline's own progress logging for the duration of the test.
    # A monitor polling this endpoint would otherwise write the full
    # preprocessing play-by-play on every poll and bury the real request logs.
    # Warnings and errors still come through, since those would mean the
    # self-test found something.
    pipeline_logger = logging.getLogger("correlation.preprocessing")
    previous_level = pipeline_logger.level
    pipeline_logger.setLevel(logging.WARNING)
    try:
        run_correlation_pipeline(frame, "time", ["a", "b"], 10, 5, "pearson")
    finally:
        pipeline_logger.setLevel(previous_level)


def _readiness_checks():
    """Return (ready, checks). Each check reports its own outcome."""
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
        checks["dependencies"] = {"ok": False, "error": str(exc)}

    try:
        _run_pipeline_self_test()
        checks["pipeline"] = {"ok": True, "detail": "self-test run completed"}
    except Exception as exc:
        ready = False
        checks["pipeline"] = {"ok": False, "error": str(exc)}

    return ready, checks


@app.route("/service-status", methods=["GET"])
def service_status():
    # CCA121: this used to return a hardcoded "running" string, which could not
    # fail while the process was alive and so told a caller nothing. It now
    # reports readiness, and answers 503 when the service cannot actually serve.
    started_at = time.perf_counter()
    ready, checks = _readiness_checks()
    check_ms = int((time.perf_counter() - started_at) * 1000)

    body = {
        # Retained so existing callers of this endpoint keep working.
        "status": "running" if ready else "degraded",
        "message": (
            "Correlation Alert Service is running."
            if ready else
            "Correlation Alert Service is running but not ready to serve requests."
        ),
        "service": "correlation-alert-api",
        # CCA121 additions.
        "live": True,
        "ready": ready,
        "checks": checks,
        "check_duration_ms": check_ms,
        "config": config.as_dict(),
    }

    if ready:
        logger.info("[HEALTH] ready=True check_ms=%d", check_ms)
    else:
        failed = [name for name, c in checks.items() if not c.get("ok")]
        logger.error("[HEALTH] ready=False failed=%s check_ms=%d", failed, check_ms)

    return jsonify(body), (200 if ready else 503)


@app.route("/detect-correlation-alert", methods=["POST"])
def detect_correlation_alert_api():
    # CCA121: every request gets a short id that is logged on each line and
    # returned to the caller, so a report of "it returned nothing" can be traced
    # to the exact run without guessing.
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

    try:
        # OPTION 1: CSV file upload using multipart/form-data
        if "file" in request.files:
            source = "file"
            uploaded_file = request.files["file"]

            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()

            timestamp_col = request.form.get("timestamp_col")
            selected_streams = request.form.get("selected_streams")
            window_size = int(request.form.get("window_size", 30))
            step_size = int(request.form.get("step_size", 5))
            method = request.form.get("method", "pearson")

            if selected_streams:
                selected_streams = [col.strip() for col in selected_streams.split(",")]

        # OPTION 2: JSON input
        else:
            source = "json"
            body = request.get_json()

            data = body.get("data")
            timestamp_col = body.get("timestamp_col")
            selected_streams = body.get("selected_streams")
            window_size = body.get("window_size", 30)
            step_size = body.get("step_size", 5)
            method = body.get("method", "pearson")

            if data is None:
                logger.warning("[%s] rejected: missing 'data' in request body",
                               request_id)
                return jsonify({
                    "error": "Missing 'data' in request body.",
                    "request_id": request_id
                }), 400

            df = pd.DataFrame(data)
            df.columns = df.columns.str.strip()

        if timestamp_col is None:
            logger.warning("[%s] rejected: missing timestamp_col", request_id)
            return jsonify({
                "error": "Missing 'timestamp_col'.",
                "request_id": request_id
            }), 400

        if selected_streams is None:
            logger.warning("[%s] rejected: missing selected_streams", request_id)
            return jsonify({
                "error": "Missing 'selected_streams'.",
                "request_id": request_id
            }), 400

        # Metadata only. The uploaded rows themselves are never logged.
        logger.info(
            "[%s] received source=%s rows_in=%d streams=%s "
            "window_size=%s step_size=%s method=%s",
            request_id, source, len(df), selected_streams,
            window_size, step_size, method
        )

        result = run_correlation_pipeline(
            df,
            timestamp_col,
            selected_streams,
            window_size,
            step_size,
            method
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
                "correlation_matrix": item["correlation_matrix"].round(4).to_dict()
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

        # A run that finishes but takes longer than the configured budget is not
        # an error, but it is the thing to look for after a slow demo.
        if runtime_ms > config.REQUEST_TIMEOUT_SECONDS * 1000:
            logger.warning(
                "[%s] slow request: runtime_ms=%d exceeded budget of %ds",
                request_id, runtime_ms, config.REQUEST_TIMEOUT_SECONDS
            )

        response = {
            "status": "success",
            "request_id": request_id,
            "runtime_ms": runtime_ms,
            "summary": {
                "processed_rows": len(result["processed_data"]),
                "windows": len(result["windows"]),
                "correlation_results": len(result["correlation_results"]),
                "changes": len(changes),
                "alerts": len(alerts),
                "non_numeric_values_coerced": data_quality.get("non_numeric_coerced", 0),
                "missing_values_imputed": data_quality.get("missing_imputed", 0)
            },
            "correlations": correlations,
            "alerts": with_iso_timestamps(alerts),
            "changes": with_iso_timestamps(changes)
        }

        return jsonify(response), 200

    # CCA112 fix (CCA109 Defect 3): bad caller input is a 400, not a 500.
    except InputValidationError as e:
        logger.warning("[%s] invalid_input after %dms: %s",
                       request_id, elapsed_ms(), e)
        return jsonify({
            "status": "error",
            "error_type": "invalid_input",
            "request_id": request_id,
            "message": str(e)
        }), 400

    except Exception as e:
        # exc_info gives the traceback in the log without returning it to the
        # caller, which would leak internal paths.
        logger.error("[%s] internal_error after %dms: %s",
                     request_id, elapsed_ms(), e, exc_info=True)
        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "request_id": request_id,
            "message": str(e)
        }), 500

if __name__ == "__main__":
    # Startup banner. The runbook tells operators to check these values first.
    logger.info("[STARTUP] Correlation Alert Service starting")
    for key, value in config.as_dict().items():
        logger.info("[STARTUP] %s=%s", key, value)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)