import io
import os
import sys

import pandas as pd
import pytest

TESTING_DIR = os.path.dirname(os.path.abspath(__file__))
CORRELATION_DIR = os.path.dirname(TESTING_DIR)

if CORRELATION_DIR not in sys.path:
    sys.path.insert(0, CORRELATION_DIR)

from server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def make_csv():
    rows = 80

    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=rows,
            freq="min",
        ),
        "sensor_a": range(rows),
        "sensor_b": [x * 2 for x in range(rows)],
        "sensor_c": [100 - x for x in range(rows)],
    })

    return io.BytesIO(
        df.to_csv(index=False).encode("utf-8")
    )


def multipart_request(**overrides):
    data = {
        "file": (make_csv(), "test.csv"),
        "timestamp_col": "timestamp",
        "selected_streams": "sensor_a,sensor_b,sensor_c",
        "method": "pearson",
    }

    data.update(overrides)
    return data


def test_documented_defaults(client):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["status"] == "success"

    config = payload["configuration"]

    assert config["window_size"] == 20
    assert config["step_size"] == 10
    assert config["method"] == "pearson"
    assert config["strong_corr_threshold"] == 0.7
    assert config["weak_corr_threshold"] == 0.4
    assert config["delta_threshold"] == 0.3


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_size", "0"),
        ("window_size", "-1"),
        ("window_size", "abc"),
        ("step_size", "0"),
        ("step_size", "-5"),
        ("step_size", "abc"),
        ("strong_corr_threshold", "1.1"),
        ("strong_corr_threshold", "-1.1"),
        ("weak_corr_threshold", "1.1"),
        ("weak_corr_threshold", "-1.1"),
        ("delta_threshold", "-0.1"),
        ("delta_threshold", "2.1"),
    ],
)
def test_invalid_configuration_returns_400(
    client,
    field,
    value,
):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(**{field: value}),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["status"] == "error"
    assert payload["error_type"] == "invalid_input"


def test_invalid_method_returns_400(client):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(
            method="banana",
        ),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["status"] == "error"
    assert payload["error_type"] == "invalid_input"
    assert "method" in payload["message"]


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "1.1",
        "2",
    ],
)
def test_valid_delta_threshold_is_accepted(
    client,
    value,
):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(
            delta_threshold=value,
        ),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["status"] == "success"
    assert (
        payload["configuration"]["delta_threshold"]
        == float(value)
    )


def test_weak_threshold_must_be_less_than_strong(client):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(
            strong_corr_threshold="0.4",
            weak_corr_threshold="0.7",
        ),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["status"] == "error"
    assert "weak_corr_threshold" in payload["message"]


def test_custom_thresholds_are_accepted(client):
    response = client.post(
        "/detect-correlation-alert",
        data=multipart_request(
            window_size="40",
            step_size="20",
            strong_corr_threshold="0.8",
            weak_corr_threshold="0.3",
            delta_threshold="0.5",
        ),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    payload = response.get_json()

    config = payload["configuration"]

    assert config["window_size"] == 40
    assert config["step_size"] == 20
    assert config["strong_corr_threshold"] == 0.8
    assert config["weak_corr_threshold"] == 0.3
    assert config["delta_threshold"] == 0.5
