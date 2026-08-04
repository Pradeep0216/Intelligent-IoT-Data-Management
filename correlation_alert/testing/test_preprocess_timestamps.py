"""Regression tests for timestamp parsing.

fix_timestamps used to call pd.to_numeric on the time column unconditionally,
so ISO 8601 and ThingSpeak created_at values became NaN and every row was
dropped, while validate_output still reported the data as clean and ready.

    cd correlation_alert && pytest testing/test_preprocess_timestamps.py -v
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import detect_correlation_change_alert, preprocess_timeseries  # noqa: E402
from preprocessing import fix_timestamps  # noqa: E402

DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "datasets",
    "nab_realtraffic",
)
TRAFFIC = os.path.join(DATA, "traffic_4stream_merged.csv")
AWS = os.path.join(DATA, "aws_control_merged.csv")

TRAFFIC_STREAMS = ["occupancy_t4013", "speed_t4013", "occupancy_6005", "speed_6005"]
AWS_STREAMS = ["ec2_cpu", "ec2_net", "elb_req"]

needs_data = pytest.mark.skipif(not os.path.exists(TRAFFIC), reason="dataset missing")


def test_numeric_counter_still_works():
    """The legacy format used by datasets/complex.csv."""
    out = fix_timestamps(pd.DataFrame({"time": [3, 1, 2], "s1": [1.0, 2.0, 3.0]}), "time")
    assert out["time"].tolist() == [1, 2, 3]
    assert pd.api.types.is_numeric_dtype(out["time"])


def test_iso_8601_is_parsed_not_dropped():
    """The defect: ISO timestamps used to drop every row."""
    df = pd.DataFrame(
        {
            "timestamp": ["2015-09-01 13:50:00", "2015-09-01 13:45:00"],
            "s1": [1.0, 2.0],
        }
    )
    out = fix_timestamps(df, "timestamp")
    assert len(out) == 2
    assert out["timestamp"].iloc[0] == pd.Timestamp("2015-09-01 13:45:00")


def test_thingspeak_created_at_is_parsed():
    """ThingSpeak created_at carries a trailing Z and must stay timezone naive."""
    df = pd.DataFrame(
        {
            "created_at": ["2026-08-04T07:53:24Z", "2026-08-04T07:52:24Z"],
            "field1": [113.0, 0.0],
        }
    )
    out = fix_timestamps(df, "created_at")
    assert out["created_at"].iloc[0] == pd.Timestamp("2026-08-04 07:52:24")
    assert out["created_at"].dt.tz is None


def test_duplicates_removed_and_sorted():
    df = pd.DataFrame(
        {
            "timestamp": [
                "2015-09-01 13:45:00",
                "2015-09-01 13:45:00",
                "2015-09-01 13:40:00",
            ],
            "s1": [1.0, 2.0, 3.0],
        }
    )
    out = fix_timestamps(df, "timestamp")
    assert len(out) == 2
    assert out["timestamp"].is_monotonic_increasing


def test_unparseable_column_raises_instead_of_emptying():
    """Silent failure was the real problem."""
    df = pd.DataFrame({"timestamp": ["nope", "still nope"], "s1": [1.0, 2.0]})
    with pytest.raises(ValueError, match="No usable timestamps"):
        fix_timestamps(df, "timestamp")


@needs_data
def test_traffic_dataset_survives_preprocessing():
    out = preprocess_timeseries(pd.read_csv(TRAFFIC), "timestamp", TRAFFIC_STREAMS)
    assert len(out) == 1850
    assert isinstance(out.index, pd.DatetimeIndex)
    assert out.index.min() == pd.Timestamp("2015-09-01 13:45:00")
    assert out.isna().sum().sum() == 0


@needs_data
def test_alert_timestamps_are_real_dates_not_1970():
    """Contract v1 requires ISO 8601 UTC. A row counter produces 1970 dates."""
    result = detect_correlation_change_alert(
        pd.read_csv(TRAFFIC), "timestamp", TRAFFIC_STREAMS, window_size=30, step_size=5
    )
    first = result["alerts"][0]
    assert first["start_time"].year == 2015
    assert first["end_time"] >= first["start_time"]


@needs_data
def test_measured_numbers_are_stable():
    """Locks the evidence numbers so a silent change fails CI."""
    result = detect_correlation_change_alert(
        pd.read_csv(TRAFFIC), "timestamp", TRAFFIC_STREAMS, window_size=30, step_size=5
    )
    assert (len(result["windows"]), len(result["changes"]), len(result["alerts"])) == (
        365,
        2184,
        77,
    )


@pytest.mark.skipif(not os.path.exists(AWS), reason="dataset missing")
def test_negative_control_false_positive_rate():
    """The AWS streams are independent, so a correct detector should stay quiet.

    It does not. This records the current rate rather than asserting it is
    acceptable, so any change to the alert logic surfaces for discussion.
    """
    result = detect_correlation_change_alert(
        pd.read_csv(AWS), "timestamp", AWS_STREAMS, window_size=30, step_size=5
    )
    assert len(result["changes"]) == 2394
    assert len(result["alerts"]) == 47
    assert len(result["alerts"]) / len(result["changes"]) == pytest.approx(0.0196, abs=0.001)
