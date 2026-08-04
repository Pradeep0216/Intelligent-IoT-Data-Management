"""
input_validator.py
Shared input validator for the Models sub-team pipeline (Week 4).

Purpose: validate raw sensor data BEFORE it is passed to any detector, so every
detector can rely on one consistent input contract instead of each one handling
malformed data differently (missing values, bad timestamps, wrong types, etc).

Owner: Deepakkumar Govindan (Week 4 — Shared Input Validator)
"""

import pandas as pd

REQUIRED_TIMESTAMP_COL = "timestamp"


class InputValidationError(Exception):
    """Raised when input sensor data does not meet the required Models input format."""
    pass


def validate_input(df: pd.DataFrame, timestamp_col: str = REQUIRED_TIMESTAMP_COL,
                    sensor_cols=None) -> pd.DataFrame:
    """
    Validate a raw sensor data DataFrame against the shared Models input format.

    Required format:
      - df must be a pandas DataFrame, not empty
      - must contain a timestamp column (default: 'timestamp'), parseable as datetime
      - timestamps must be unique (duplicates rejected)
      - must contain at least one numeric sensor value column
      - sensor columns must not contain NaN / missing values
      - sensor columns must be numeric (int or float)

    Returns:
      A validated copy of the DataFrame, sorted by timestamp and indexed by it
      (this matches the existing detector output contract, which also indexes by timestamp).

    Raises:
      InputValidationError with a specific, readable message describing exactly
      what failed and why — so callers (Pradeep's detector runner, Kimheang's
      tests) get a clear signal instead of a downstream crash.
    """
    if not isinstance(df, pd.DataFrame):
        raise InputValidationError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    if df.empty:
        raise InputValidationError("Input DataFrame is empty — no rows to process")

    if timestamp_col not in df.columns:
        raise InputValidationError(
            f"Missing required timestamp column '{timestamp_col}'. Found columns: {list(df.columns)}"
        )

    df = df.copy()

    try:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    except Exception as e:
        raise InputValidationError(f"Column '{timestamp_col}' could not be parsed as datetime: {e}")

    if df[timestamp_col].duplicated().any():
        dupes = df[timestamp_col][df[timestamp_col].duplicated()].tolist()
        preview = dupes[:5]
        raise InputValidationError(
            f"Duplicate timestamps found: {preview}{' ...' if len(dupes) > 5 else ''}"
        )

    df = df.sort_values(timestamp_col).reset_index(drop=True)

    if sensor_cols is None:
        sensor_cols = [c for c in df.columns if c != timestamp_col]

    if not sensor_cols:
        raise InputValidationError("No sensor value columns found besides the timestamp column")

    missing_cols = [c for c in sensor_cols if c not in df.columns]
    if missing_cols:
        raise InputValidationError(f"Declared sensor columns not found in data: {missing_cols}")

    non_numeric = [c for c in sensor_cols if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise InputValidationError(f"Sensor column(s) are not numeric: {non_numeric}")

    nan_report = {c: int(df[c].isna().sum()) for c in sensor_cols if df[c].isna().any()}
    if nan_report:
        raise InputValidationError(f"Missing (NaN) values found in sensor columns: {nan_report}")

    return df.set_index(timestamp_col)


if __name__ == "__main__":
    good = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="h"),
        "s1": [10.1, 10.3, 10.2, 50.9, 10.4],
        "s2": [5.0, 5.1, 5.0, 5.2, 5.1],
    })
    print("=== Test 1: valid input ===")
    validated = validate_input(good)
    print(validated)
    print("PASSED\n")

    bad_missing = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="h"),
        "s1": [10.1, None, 10.2, 50.9, 10.4],
        "s2": [5.0, 5.1, 5.0, 5.2, 5.1],
    })
    print("=== Test 2: missing value in sensor column ===")
    try:
        validate_input(bad_missing)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}\n")

    bad_dupe = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00", "2026-01-01 00:00", "2026-01-01 02:00"],
        "s1": [10.1, 10.3, 10.2],
    })
    print("=== Test 3: duplicate timestamps ===")
    try:
        validate_input(bad_dupe)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}\n")

    bad_col = pd.DataFrame({"time": ["2026-01-01"], "s1": [10.1]})
    print("=== Test 4: missing timestamp column ===")
    try:
        validate_input(bad_col)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}")
