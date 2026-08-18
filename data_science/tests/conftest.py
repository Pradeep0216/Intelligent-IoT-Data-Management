import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# The pipeline/detector/runner modules use bare intra-package imports (e.g.
# "from detectors.iforest_detector import ..." and "import input_validator"),
# so data_science/ itself needs to be on sys.path, not just the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Normal / stable sensor data
# ---------------------------------------------------------------------------

@pytest.fixture
def make_normal_df():
    """Factory fixture: build a DatetimeIndex-ed DataFrame of stable, low-variance
    sensor readings -- no injected anomalies. Indexed by a DatetimeIndex (rather
    than a 'timestamp' column) to match the shape preprocessor.py hands detectors
    in the real pipeline, and the first branch of input_validator.validate_input().
    """
    def _make(rows=200, sensor_cols=("s1", "s2"), seed=42):
        idx = pd.date_range("2024-01-01", periods=rows, freq="s")
        rng = np.random.default_rng(seed)
        data = {col: rng.normal(loc=10.0, scale=1.0, size=rows) for col in sensor_cols}
        return pd.DataFrame(data, index=idx)
    return _make


@pytest.fixture
def normal_df(make_normal_df):
    return make_normal_df()


# ---------------------------------------------------------------------------
# Failure-case fixtures: empty data / bad timestamps
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_df():
    return pd.DataFrame()


@pytest.fixture
def df_unparseable_timestamp():
    """A literal 'timestamp' column with values that aren't dates at all."""
    return pd.DataFrame({
        "timestamp": ["not-a-date", "also-not-a-date", "still-not-a-date"],
        "s1": [1.0, 2.0, 3.0],
        "s2": [4.0, 5.0, 6.0],
    })


@pytest.fixture
def df_implausible_numeric_timestamp():
    """A literal 'timestamp' column that's numeric but parses to implausible
    (pre-2000) dates -- e.g. a raw sample-elapsed-seconds column mislabeled
    'timestamp' rather than 'time'."""
    return pd.DataFrame({
        "timestamp": [0, 0.01, 0.02, 0.03],
        "s1": [1.0, 1.01, 1.02, 1.03],
        "s2": [2.0, 2.01, 2.02, 2.03],
    })


@pytest.fixture
def df_duplicate_timestamps():
    return pd.DataFrame({
        "timestamp": [
            "2024-01-01 00:00:00",
            "2024-01-01 00:00:00",
            "2024-01-01 00:00:01",
        ],
        "s1": [1.0, 999.0, 1.1],
        "s2": [2.0, 999.0, 2.1],
    })
