from io import BytesIO

import pytest

from correlation_alert.server import create_app


def _payload(delta_threshold):
    return {
        "data": [
            {"time": 1, "sensor_a": 1, "sensor_b": 1},
            {"time": 2, "sensor_a": 2, "sensor_b": 2},
            {"time": 3, "sensor_a": 3, "sensor_b": 3},
            {"time": 4, "sensor_a": 4, "sensor_b": 4},
            {"time": 5, "sensor_a": 5, "sensor_b": 6},
            {"time": 6, "sensor_a": 6, "sensor_b": 5},
        ],
        "timestamp_col": "time",
        "selected_streams": ["sensor_a", "sensor_b"],
        "window_size": 3,
        "step_size": 3,
        "delta_threshold": delta_threshold,
    }


def test_service_status_reports_running_service():
    client = create_app().test_client()

    response = client.get("/service-status")

    assert response.status_code == 200
    assert response.get_json()["status"] == "running"
    assert response.get_json()["service"] == "correlation-alert-api"


def test_csv_upload_returns_pipeline_response():
    client = create_app().test_client()
    csv_data = b"time,s1,s2\n1,10,20\n2,11,21\n3,12,22\n4,13,23\n"

    response = client.post(
        "/detect-correlation-alert",
        data={
            "file": (BytesIO(csv_data), "sensors.csv"),
            "timestamp_col": "time",
            "selected_streams": "s1,s2",
            "window_size": "2",
            "step_size": "2",
            "method": "pearson",
        },
        content_type="multipart/form-data",
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["summary"]["processed_rows"] == 4
    assert body["summary"]["windows"] == 2
    assert len(body["correlations"]) == 2
    assert len(body["changes"]) == 1
    assert body["alerts"] == []


def test_api_uses_custom_delta_threshold():
    client = create_app().test_client()

    response = client.post("/detect-correlation-alert", json=_payload(0.6))

    assert response.status_code == 200
    assert response.get_json()["summary"]["alerts"] == 0


@pytest.mark.parametrize("method", ["pearson", "spearman", "kendall"])
def test_api_accepts_supported_method(method):
    client = create_app().test_client()
    payload = _payload(0.6)
    payload["method"] = method

    response = client.post("/detect-correlation-alert", json=payload)

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"


def test_invalid_method_returns_400():
    client = create_app().test_client()
    payload = _payload(0.6)
    payload["method"] = "banana"

    response = client.post("/detect-correlation-alert", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error_type"] == "invalid_input"


def test_invalid_threshold_returns_400():
    client = create_app().test_client()

    response = client.post("/detect-correlation-alert", json=_payload("abc"))

    assert response.status_code == 400
    assert response.get_json()["error_type"] == "invalid_input"
