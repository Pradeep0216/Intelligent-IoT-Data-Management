import json
from pathlib import Path

from analytics_validation.response_validator import validate_response


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename):
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


def test_valid_anomaly_response():
    response = load_fixture("valid_anomaly.json")
    is_valid, errors = validate_response(response)

    assert is_valid is True
    assert errors == []


def test_valid_correlation_response():
    response = load_fixture("valid_correlation.json")
    is_valid, errors = validate_response(response)

    assert is_valid is True
    assert errors == []


def test_invalid_anomaly_response():
    response = load_fixture("invalid_anomaly.json")
    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "Invalid ISO 8601 timestamp" in errors
    assert "Unsupported alert type: fault" in errors
    assert "target must be a string" in errors
    assert "score must be numeric" in errors
    assert "Unsupported severity: urgent" in errors
    assert "supporting_values must be an object" in errors


def test_invalid_correlation_response():
    response = load_fixture("invalid_correlation.json")
    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "Missing required field: target" in errors
    assert "Invalid ISO 8601 timestamp" in errors
    assert "score must be numeric" in errors
    assert "Unsupported severity: extreme" in errors
    assert "message must be a string" in errors
    assert "supporting_values must be an object" in errors


def test_empty_timestamp():
    response = {
        "timestamp": "",
        "alert_type": "anomaly",
        "target": "sensor-001",
        "method": "IsolationForest",
        "score": 0.95,
        "severity": "high",
        "message": "Anomaly detected",
        "supporting_values": {}
    }

    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "Invalid ISO 8601 timestamp" in errors


def test_empty_string_fields():
    response = {
        "timestamp": "2026-08-07T10:00:00Z",
        "alert_type": "anomaly",
        "target": "",
        "method": "",
        "score": 0.95,
        "severity": "high",
        "message": "",
        "supporting_values": {}
    }

    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "target must not be empty" in errors
    assert "method must not be empty" in errors
    assert "message must not be empty" in errors


def test_null_values():
    response = {
        "timestamp": None,
        "alert_type": None,
        "target": None,
        "method": None,
        "score": None,
        "severity": None,
        "message": None,
        "supporting_values": None
    }

    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "timestamp must be a string" in errors
    assert "alert_type must be a string" in errors
    assert "target must be a string" in errors
    assert "method must be a string" in errors
    assert "score must be numeric" in errors
    assert "severity must be a string" in errors
    assert "message must be a string" in errors
    assert "supporting_values must be an object" in errors


def test_multiple_missing_required_fields():
    response = {
        "timestamp": "2026-08-07T10:00:00Z"
    }

    is_valid, errors = validate_response(response)

    assert is_valid is False
    assert "Missing required field: alert_type" in errors
    assert "Missing required field: target" in errors
    assert "Missing required field: method" in errors
    assert "Missing required field: score" in errors
    assert "Missing required field: severity" in errors
    assert "Missing required field: message" in errors
    assert "Missing required field: supporting_values" in errors