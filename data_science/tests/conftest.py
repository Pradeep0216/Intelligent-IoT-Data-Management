import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Shared DataFrame builders for input_validator.py test cases
# ---------------------------------------------------------------------------

@pytest.fixture
def make_valid_df():
    """Factory fixture: build a structurally-valid timestamp + sensor DataFrame."""
    def _make(rows=50, sensor_cols=("s1", "s2")):
        idx = pd.date_range("2024-01-01", periods=rows, freq="s")
        data = {"timestamp": idx.astype(str)}
        rng = np.random.default_rng(42)
        for col in sensor_cols:
            data[col] = rng.normal(loc=10.0, scale=1.0, size=rows)
        return pd.DataFrame(data)
    return _make


@pytest.fixture
def valid_df(make_valid_df):
    return make_valid_df()


@pytest.fixture
def empty_df():
    return pd.DataFrame()


@pytest.fixture
def df_missing_timestamp_col():
    return pd.DataFrame({"s1": [1.0, 2.0, 3.0], "s2": [4.0, 5.0, 6.0]})


@pytest.fixture
def df_missing_sensor_values():
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=4, freq="s").astype(str),
        "s1": [1.0, None, 1.2, 1.3],
        "s2": [2.0, 2.1, None, 2.3],
    })


@pytest.fixture
def df_non_numeric_sensor():
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=3, freq="s").astype(str),
        "s1": [1.0, 2.0, 3.0],
        "s2": ["abc", "def", "ghi"],
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


# ---------------------------------------------------------------------------
# detector_runner.py workaround fixture
# ---------------------------------------------------------------------------
# KNOWN BUG (see test_detector_runner_import_currently_broken in
# test_shared_models_workflow.py): detector_runner.py does
#     from detectors.isolation_forest_detector import IsolationForestDetector
# but the real module on this branch is detectors/iforest_detector.py, so a
# plain `import detector_runner` fails before run_detector() is even
# reachable. This fixture registers a stub module at the path
# detector_runner.py expects (pointing at the real IsolationForestDetector),
# so the rest of run_detector()'s branch logic -- unknown detector names,
# the success path, error handling -- can still be exercised in isolation
# from that specific bug.
#
# Delete this fixture (and update the tests that use it) once Pradeep fixes
# the import in detector_runner.py.

@pytest.fixture
def detector_runner_module(monkeypatch):
    import detectors.iforest_detector as real_iforest

    stub = types.ModuleType("detectors.isolation_forest_detector")
    stub.IsolationForestDetector = real_iforest.IsolationForestDetector
    monkeypatch.setitem(sys.modules, "detectors.isolation_forest_detector", stub)

    sys.modules.pop("detector_runner", None)
    import detector_runner
    yield detector_runner
    sys.modules.pop("detector_runner", None)
