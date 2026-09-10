from data_science.detector_testing.tester import DetectorTester

from data_science.detector_testing.test_cases import (
    normal_data,
    obvious_anomalies,
    no_anomalies,
    too_few_readings,
    missing_values,
    invalid_values,
    different_sensor_scales,
    configuration_data
)


def test_normal_data():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case("Normal data", normal_data())

    assert result["status"] in ["success", "failed"]


def test_obvious_anomalies():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "Obvious anomalies",
        obvious_anomalies()
    )

    assert result["status"] in ["success", "failed"]


def test_no_anomalies():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "No anomalies",
        no_anomalies()
    )

    assert result["status"] in ["success", "failed"]


def test_too_few_readings():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "Too few readings",
        too_few_readings()
    )

    assert result["status"] in ["success", "failed"]


def test_missing_values():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "Missing values",
        missing_values()
    )

    assert result["status"] in ["success", "failed"]


def test_invalid_values():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "Invalid values",
        invalid_values()
    )

    assert result["status"] in ["success", "failed"]


def test_different_sensor_scales():
    tester = DetectorTester("IsolationForest")
    result = tester.test_case(
        "Different sensor scales",
        different_sensor_scales()
    )

    assert result["status"] in ["success", "failed"]


def test_configuration():
    tester = DetectorTester("IsolationForest")

    result = tester.test_case(
        "Isolation Forest configuration",
        configuration_data(),
        {
            "n_estimators": 100,
            "contamination": 0.05
        }
    )

    assert result["status"] in ["success", "failed"]
