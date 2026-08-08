from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd

from main import detect_correlation_change_alert as run_correlation_pipeline
from main import to_iso8601, with_iso_timestamps
from preprocessing import InputValidationError


app = Flask(__name__)
CORS(app)



DEFAULT_WINDOW_SIZE = 20
DEFAULT_STEP_SIZE = 10
DEFAULT_METHOD = "pearson"

DEFAULT_STRONG_CORR_THRESHOLD = 0.7
DEFAULT_WEAK_CORR_THRESHOLD = 0.4
DEFAULT_DELTA_THRESHOLD = 0.3



def parse_positive_int(value, name):
    """
    Convert a request value to a positive integer.

    Raises:
        InputValidationError:
            If the value cannot be converted to an integer
            or is less than/equal to zero.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise InputValidationError(
            f"'{name}' must be a positive integer."
        )

    if parsed <= 0:
        raise InputValidationError(
            f"'{name}' must be a positive integer."
        )

    return parsed


def parse_correlation_threshold(value, name):
    """
    Convert a request value to float and validate that
    it is inside the correlation range [-1, 1].

    Raises:
        InputValidationError:
            If the value is not numeric or is outside [-1, 1].
    """
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise InputValidationError(
            f"'{name}' must be a number between -1 and 1."
        )

    if parsed < -1 or parsed > 1:
        raise InputValidationError(
            f"'{name}' must be between -1 and 1."
        )

    return parsed


def validate_configuration(
    window_size,
    step_size,
    strong_corr_threshold,
    weak_corr_threshold,
    delta_threshold,
):
    """
    Validate all configurable correlation alert parameters.

    Rules:
        - window_size must be a positive integer
        - step_size must be a positive integer
        - thresholds must be within [-1, 1]
        - weak_corr_threshold must be less than
          strong_corr_threshold
    """

    window_size = parse_positive_int(
        window_size,
        "window_size",
    )

    step_size = parse_positive_int(
        step_size,
        "step_size",
    )

    strong_corr_threshold = parse_correlation_threshold(
        strong_corr_threshold,
        "strong_corr_threshold",
    )

    weak_corr_threshold = parse_correlation_threshold(
        weak_corr_threshold,
        "weak_corr_threshold",
    )

    delta_threshold = parse_correlation_threshold(
        delta_threshold,
        "delta_threshold",
    )

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


@app.route("/service-status", methods=["GET"])
def service_status():
    return jsonify({
        "status": "running",
        "message": "Correlation Alert Service is running.",
        "service": "correlation-alert-api",
    })


@app.route("/detect-correlation-alert", methods=["POST"])
def detect_correlation_alert_api():

    try:


        if "file" in request.files:

            uploaded_file = request.files["file"]

            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()

            timestamp_col = request.form.get(
                "timestamp_col"
            )

            selected_streams = request.form.get(
                "selected_streams"
            )

            window_size = request.form.get(
                "window_size",
                DEFAULT_WINDOW_SIZE,
            )

            step_size = request.form.get(
                "step_size",
                DEFAULT_STEP_SIZE,
            )

            method = request.form.get(
                "method",
                DEFAULT_METHOD,
            )

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

            if selected_streams:
                selected_streams = [
                    col.strip()
                    for col in selected_streams.split(",")
                ]


        else:

            body = request.get_json(silent=True)

            if body is None:
                return jsonify({
                    "status": "error",
                    "error_type": "invalid_input",
                    "message": (
                        "Request must contain either a CSV file "
                        "or a valid JSON body."
                    ),
                }), 400

            data = body.get("data")

            timestamp_col = body.get(
                "timestamp_col"
            )

            selected_streams = body.get(
                "selected_streams"
            )

            window_size = body.get(
                "window_size",
                DEFAULT_WINDOW_SIZE,
            )

            step_size = body.get(
                "step_size",
                DEFAULT_STEP_SIZE,
            )

            method = body.get(
                "method",
                DEFAULT_METHOD,
            )

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
                return jsonify({
                    "status": "error",
                    "error_type": "invalid_input",
                    "message": "Missing 'data' in request body.",
                }), 400

            df = pd.DataFrame(data)
            df.columns = df.columns.str.strip()



        if timestamp_col is None:
            return jsonify({
                "status": "error",
                "error_type": "invalid_input",
                "message": "Missing 'timestamp_col'.",
            }), 400

        if selected_streams is None:
            return jsonify({
                "status": "error",
                "error_type": "invalid_input",
                "message": "Missing 'selected_streams'.",
            }), 400

        # JSON selected_streams should be a list.
        # Multipart selected_streams is converted above from CSV text.

        if isinstance(selected_streams, str):
            selected_streams = [
                col.strip()
                for col in selected_streams.split(",")
                if col.strip()
            ]

        if not selected_streams:
            return jsonify({
                "status": "error",
                "error_type": "invalid_input",
                "message": (
                    "'selected_streams' must contain at least "
                    "one stream."
                ),
            }), 400



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



        result = run_correlation_pipeline(
            df=df,
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


        # Format correlation results
        correlations = []

        for item in result["correlation_results"]:

            correlations.append({
                "window_index": item["window_index"],
                "start_time": to_iso8601(
                    item["start_time"]
                ),
                "end_time": to_iso8601(
                    item["end_time"]
                ),
                "window_size": item["window_size"],
                "correlation_matrix": (
                    item["correlation_matrix"]
                    .round(4)
                    .to_dict()
                ),
            })

        data_quality = result.get(
            "data_quality",
            {},
        )


        # Response
        response = {

            "status": "success",

            # Important for CCA115 evidence:
            # shows which settings were actually applied.
            "configuration": {
                "window_size": window_size,
                "step_size": step_size,
                "method": method,
                "strong_corr_threshold": (
                    strong_corr_threshold
                ),
                "weak_corr_threshold": (
                    weak_corr_threshold
                ),
                "delta_threshold": (
                    delta_threshold
                ),
            },

            "summary": {
                "processed_rows": len(
                    result["processed_data"]
                ),
                "windows": len(
                    result["windows"]
                ),
                "correlation_results": len(
                    result["correlation_results"]
                ),
                "changes": len(changes),
                "alerts": len(alerts),
                "non_numeric_values_coerced": (
                    data_quality.get(
                        "non_numeric_coerced",
                        0,
                    )
                ),
                "missing_values_imputed": (
                    data_quality.get(
                        "missing_imputed",
                        0,
                    )
                ),
            },

            "correlations": correlations,

            "alerts": with_iso_timestamps(
                alerts
            ),

            "changes": with_iso_timestamps(
                changes
            ),
        }

        return jsonify(response), 200


    # Invalid caller input -> HTTP 400
    except InputValidationError as e:

        return jsonify({
            "status": "error",
            "error_type": "invalid_input",
            "message": str(e),
        }), 400

    # Unexpected server error -> HTTP 500
    except Exception as e:

        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "message": str(e),
        }), 500


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5001,
    )
