"""
[AIntg-002] Analytics Intelligence E2E Integration Runner

Runs one real dataset through:

Models:
Dataset
-> Models Input Validator
-> IsolationForest detector runner
-> Models Draft V0.1 adapter

Correlation:
Dataset
-> Correlation API
-> Correlation Draft V0.1 adapter

Then:
Models alerts + Correlation alerts
-> Shared Envelope Builder
-> Shared Response Validator
-> Final Draft V0.1 Analytics JSON
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from data_science.input_validator import validate_input
from data_science.detector_runner import run_detector
from data_science.adapters.models_output_adapter import adapt_models_output

from correlation_alert.server import create_app

from analytics_integration.adapters.correlation_adapter import (
    adapt_correlation_response,
)
from analytics_integration.builders.envelope_builder import (
    build_analytics_response,
)

from analytics_validation.response_validator import (
    validate_alert,
    validate_response,
)


# ---------------------------------------------------------
# PATHS / SMOKE TEST CONFIGURATION
# ---------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATASET_PATH = (
    REPO_ROOT
    / "datasets"
    / "nab_realtraffic"
    / "traffic_4stream_merged.csv"
)

# Keep the smoke test reasonably fast while still using real data.
DEFAULT_ROW_LIMIT = 300

# Models will test one real sensor stream.
MODEL_METRIC = "occupancy_t4013"

# Correlation needs at least two streams.
CORRELATION_STREAMS = [
    "occupancy_t4013",
    "occupancy_6005",
]

CORRELATION_WINDOW_SIZE = 20
CORRELATION_STEP_SIZE = 10
CORRELATION_METHOD = "pearson"


# ---------------------------------------------------------
# DATASET
# ---------------------------------------------------------

def load_smoke_dataset(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    row_limit: int | None = DEFAULT_ROW_LIMIT,
) -> pd.DataFrame:
    """
    Load the shared traffic dataset used by the AIntl smoke test.
    """

    dataset_path = Path(dataset_path)

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"E2E dataset was not found: {dataset_path}"
        )

    df = pd.read_csv(dataset_path)

    required_columns = {
        "timestamp",
        MODEL_METRIC,
        *CORRELATION_STREAMS,
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"E2E dataset is missing required columns: {sorted(missing)}"
        )

    if row_limit is not None:
        df = df.head(row_limit).copy()

    if df.empty:
        raise ValueError("E2E dataset contains no rows.")

    return df


# ---------------------------------------------------------
# MODELS PATH
# ---------------------------------------------------------

def run_models_path(
    df: pd.DataFrame,
) -> tuple[list[dict], dict]:
    """
    Run:

    Dataset
    -> Models input validator
    -> IsolationForest
    -> Models V0.1 adapter
    """

    model_df = df[
        [
            "timestamp",
            MODEL_METRIC,
        ]
    ].copy()

    # 1. Validate Models input.
    validated_df = validate_input(
        model_df,
        timestamp_col="timestamp",
        sensor_cols=[MODEL_METRIC],
        min_readings=20,
    )

    # 2. Run the real Models detector runner.
    raw_model_result = run_detector(
        detector_name="isolationforest",
        dataframe=validated_df[[MODEL_METRIC]],
    )

    if raw_model_result.get("status") != "success":
        raise RuntimeError(
            "Models runtime failed: "
            f"{raw_model_result.get('error', 'unknown error')}"
        )

    # 3. Give the Models adapter the source context it needs.
    input_context = {
        "entity_id": "nab_realtraffic",
        "metrics": [MODEL_METRIC],
        "sensor_values": validated_df[
            MODEL_METRIC
        ].tolist(),
    }

    # 4. Convert native Models output -> Draft V0.1 alerts.
    models_alerts = adapt_models_output(
        raw_model_result,
        input_context,
    )

    # 5. Validate each adapted Models alert before building envelope.
    for index, alert in enumerate(models_alerts):
        errors = validate_alert(alert)

        if errors:
            raise ValueError(
                f"Models alert {index} failed V0.1 validation: {errors}"
            )

    return models_alerts, raw_model_result


# ---------------------------------------------------------
# CORRELATION PATH
# ---------------------------------------------------------

def run_correlation_path(
    df: pd.DataFrame,
) -> tuple[list[dict], dict]:
    """
    Run:

    Dataset
    -> real Correlation Flask API
    -> Correlation V0.1 adapter

    Flask test_client is used so the actual API boundary is tested
    without needing to manually start another terminal/server.
    """

    correlation_df = df[
        [
            "timestamp",
            *CORRELATION_STREAMS,
        ]
    ].copy()

    request_payload = {
        "data": correlation_df.to_dict(
            orient="records"
        ),
        "timestamp_col": "timestamp",
        "selected_streams": CORRELATION_STREAMS,
        "window_size": CORRELATION_WINDOW_SIZE,
        "step_size": CORRELATION_STEP_SIZE,
        "method": CORRELATION_METHOD,
    }

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.post(
            "/detect-correlation-alert",
            json=request_payload,
        )

    raw_correlation_response = response.get_json()

    if response.status_code != 200:
        raise RuntimeError(
            "Correlation API failed. "
            f"HTTP {response.status_code}: "
            f"{raw_correlation_response}"
        )

    if (
        not isinstance(raw_correlation_response, dict)
        or raw_correlation_response.get("status") != "success"
    ):
        raise RuntimeError(
            "Correlation API returned an unexpected response: "
            f"{raw_correlation_response}"
        )

    # Use the REAL configuration returned by Correlation.
    #
    # This prevents AIntl from accidentally using old fallback
    # values such as window=30 / step=5 when Correlation is
    # actually running window=20 / step=10.
    request_context = raw_correlation_response.get(
        "configuration",
        {},
    )

    correlation_alerts = adapt_correlation_response(
        raw_correlation_response,
        request_context=request_context,
    )

    # Validate each adapted Correlation alert.
    for index, alert in enumerate(correlation_alerts):
        errors = validate_alert(alert)

        if errors:
            raise ValueError(
                f"Correlation alert {index} "
                f"failed V0.1 validation: {errors}"
            )

    return correlation_alerts, raw_correlation_response


# ---------------------------------------------------------
# COMPLETE AINTL E2E
# ---------------------------------------------------------

def run_mvp_pipeline(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    row_limit: int | None = DEFAULT_ROW_LIMIT,
) -> dict:
    """
    Execute the complete Analytics Intelligence smoke-test path.
    """

    # 1. Simulated Backend input.
    df = load_smoke_dataset(
        dataset_path=dataset_path,
        row_limit=row_limit,
    )

    # 2. Models path.
    models_alerts, _ = run_models_path(df)

    # 3. Correlation path.
    correlation_alerts, _ = run_correlation_path(df)

    # 4. Build one shared Analytics response.
    final_response = build_analytics_response(
        models_alerts=models_alerts,
        correlation_alerts=correlation_alerts,
        processed_items=len(df),
    )

    # 5. Validate the final Draft V0.1 response.
    validation_errors = validate_response(
        final_response
    )

    if validation_errors:
        raise ValueError(
            "Final Analytics response failed V0.1 validation: "
            f"{validation_errors}"
        )

    # 6. Final JSON serialisation check.
    json.dumps(final_response)

    return final_response


# ---------------------------------------------------------
# MANUAL RUNNER
# ---------------------------------------------------------

def main():
    response = run_mvp_pipeline()

    alert_types = sorted(
        {
            alert["alert_type"]
            for alert in response["alerts"]
        }
    )

    print()
    print("============================================")
    print(" AINTL E2E SMOKE TEST SUCCESS")
    print("============================================")
    print(
        "Status:",
        response["status"],
    )
    print(
        "Processed items:",
        response["summary"]["processed_items"],
    )
    print(
        "Total alerts:",
        response["summary"]["alert_count"],
    )
    print(
        "Alert types:",
        alert_types,
    )
    print(
        "Errors:",
        response["errors"],
    )
    print("Final response is valid Draft V0.1 JSON.")
    print("============================================")


if __name__ == "__main__":
    main()