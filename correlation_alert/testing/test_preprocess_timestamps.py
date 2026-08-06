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
from main import (  # noqa: E402
    detect_correlation_change_alert,
    preprocess_timeseries,
    to_iso8601,
    with_iso_timestamps,
)
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


def test_mostly_dates_with_some_numbers_picks_datetime():
    """Boundary on the numeric_share >= 0.5 rule.

    Two of five values parse as numbers, so the share is 0.4 and the column
    must be read as dates. If the rule ever flips, the three real dates become
    NaN and get dropped, which is the original defect in miniature.
    """
    df = pd.DataFrame(
        {
            "timestamp": [
                "2015-09-01 13:40:00",
                "2015-09-01 13:45:00",
                "2015-09-01 13:50:00",
                "1",
                "2",
            ],
            "s1": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    out = fix_timestamps(df, "timestamp")
    assert len(out) == 3
    assert pd.api.types.is_datetime64_any_dtype(out["timestamp"])


def test_iso8601_serialiser_matches_contract_v1():
    """Contract v1 pins ISO 8601 UTC with a trailing Z."""
    assert to_iso8601(pd.Timestamp("2015-09-01 21:05:00")) == "2015-09-01T21:05:00Z"
    assert to_iso8601(pd.Timestamp("2015-09-01 21:05:00", tz="UTC")) == "2015-09-01T21:05:00Z"
    assert to_iso8601(None) is None
    # A numeric time column has no real date, so it must not become a 1970 value.
    assert to_iso8601(150) == 150


def test_api_layer_does_not_emit_rfc_1123():
    """Flask serialises a bare pandas Timestamp as 'Tue, 01 Sep 2015 ... GMT'.

    with_iso_timestamps has to run before jsonify sees the payload.
    """
    records = [{"start_time": pd.Timestamp("2015-09-01 21:05:00"), "delta": 0.35}]
    out = with_iso_timestamps(records)
    assert out[0]["start_time"] == "2015-09-01T21:05:00Z"
    assert "GMT" not in out[0]["start_time"]
    assert out[0]["delta"] == 0.35


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
