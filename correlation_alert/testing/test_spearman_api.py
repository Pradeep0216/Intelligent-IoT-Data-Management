import io
import os
import sys

import pandas as pd
import pytest


# Allow the test to import server.py from correlation_alert/
CORRELATION_ALERT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if CORRELATION_ALERT_DIR not in sys.path:
    sys.path.insert(0, CORRELATION_ALERT_DIR)

from server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def create_test_csv():
    """Create a small valid multivariate time-series CSV in memory."""

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-01-01",
                periods=100,
                freq="min",
            ),
            "sensor_a": list(range(100)),
            "sensor_b": [value * 2 for value in range(100)],
            "sensor_c": [100 - value for value in range(100)],
        }
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8")

    return io.BytesIO(csv_bytes)


def test_spearman_returns_200(client):
    response = client.post(
        "/detect-correlation-alert",
        data={
            "file": (
                create_test_csv(),
                "spearman_test.csv",
            ),
            "timestamp_col": "timestamp",
            "selected_streams": "sensor_a,sensor_b,sensor_c",
            "window_size": "20",
            "step_size": "10",
            "method": "spearman",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload is not None
    assert payload.get("status") == "success"
