"""
input_validator.py (v2.1 — Week 5, PR #5 review round 1)
Shared input validator for the Models sub-team pipeline.

v2 changes (Week 5 — "lock the input boundary"):
  - Adds sensor_id / sensor_id_col support so downstream results can be traced
    back to a physical sensor (was a known gap in v1).
  - Adds min_rows enforcement.
  - Fixes a real bug found during Week 4 testing: a numeric column (e.g. a plain
    sample index like 0, 0.01, 0.02 ...) would silently parse as a valid datetime
    via pandas, producing meaningless dates near 1970-01-01 instead of raising an
    error. v2 detects this and rejects it unless the caller explicitly
    acknowledges the column is an index, not real calendar time.

v2.1 fix (addressing Lucas's review of PR #5):
  - sensor_id_col now actually normalises to a column literally named
    'sensor_id' in the output, matching what the documentation already
    promised. Previously the original column name was kept as-is, which was
    inconsistent with the documented contract.

Owner: Deepakkumar Govindan (Week 5 — Input boundary validator + pipeline integration)
"""

import pandas as pd

REQUIRED_TIMESTAMP_COL = "timestamp"
MIN_PLAUSIBLE_YEAR = 2000  # timestamps parsing to before this are almost certainly not real calendar time


class InputValidationError(Exception):
    """Raised when input sensor data does not meet the required Models input format."""
    pass


def validate_input(
    df: pd.DataFrame,
    timestamp_col: str = REQUIRED_TIMESTAMP_COL,
    sensor_cols=None,
    sensor_id: str = None,
    sensor_id_col: str = None,
    min_rows: int = 1,
    timestamp_is_index: bool = False,
) -> pd.DataFrame:
    """
    Validate a raw sensor data DataFrame against the shared Models input format (v2).

    Required format:
      - df must be a pandas DataFrame, not empty, with at least `min_rows` rows
      - must contain a timestamp column (default: 'timestamp'), parseable as datetime
      - timestamps must be unique (duplicates rejected) and are sorted
      - must contain at least one numeric sensor value column
      - sensor columns must not contain NaN / missing values
      - sensor columns must be numeric (int or float)

    New in v2:
      - sensor_id: pass a single sensor ID string to tag every row (common case:
        one file = one device). Mutually exclusive with sensor_id_col.
      - sensor_id_col: alternatively, a column in df already containing a
        per-row sensor/device ID. Mutually exclusive with sensor_id.
      - min_rows: reject data with fewer than this many rows.
      - timestamp_is_index: if the timestamp column is actually a numeric sample
        index (not real calendar time), you must pass True to acknowledge this.
        Otherwise, a numeric timestamp column that parses to implausible dates
        (all before year 2000) is rejected with a clear error instead of silently
        producing meaningless 1970-epoch dates.

    Returns:
      A validated copy of the DataFrame, sorted by timestamp and indexed by it.
      If sensor_id / sensor_id_col was provided, a 'sensor_id' column is present
      (constant value for sensor_id, passthrough for sensor_id_col).

    Raises:
      InputValidationError with a specific, readable message describing exactly
      what failed and why.
    """
    if not isinstance(df, pd.DataFrame):
        raise InputValidationError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    if df.empty:
        raise InputValidationError("Input DataFrame is empty — no rows to process")

    if len(df) < min_rows:
        raise InputValidationError(f"Not enough rows: got {len(df)}, minimum required is {min_rows}")

    if timestamp_col not in df.columns:
        raise InputValidationError(
            f"Missing required timestamp column '{timestamp_col}'. Found columns: {list(df.columns)}"
        )

    if sensor_id is not None and sensor_id_col is not None:
        raise InputValidationError("Provide either sensor_id or sensor_id_col, not both")

    if sensor_id_col is not None and sensor_id_col not in df.columns:
        raise InputValidationError(f"sensor_id_col '{sensor_id_col}' not found in data. Found columns: {list(df.columns)}")

    df = df.copy()

    was_numeric_timestamp = pd.api.types.is_numeric_dtype(df[timestamp_col])

    if was_numeric_timestamp and timestamp_is_index:
        # Treat as a plain sortable index — do NOT convert to a datetime. Converting
        # small fractional numbers (e.g. 0, 0.01, 0.02 seconds-elapsed) via
        # pd.to_datetime rounds them to nanoseconds and collapses them into
        # duplicate timestamps. Keep the raw numeric values instead.
        pass
    else:
        try:
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        except Exception as e:
            raise InputValidationError(f"Column '{timestamp_col}' could not be parsed as datetime: {e}")

        # v2 fix: catch numeric columns that "parse" as datetime but aren't real calendar time
        if was_numeric_timestamp:
            implausible = (df[timestamp_col].dt.year < MIN_PLAUSIBLE_YEAR).all()
            if implausible:
                example = df[timestamp_col].iloc[0]
                raise InputValidationError(
                    f"Column '{timestamp_col}' is numeric and parsed to implausible dates "
                    f"(all before year {MIN_PLAUSIBLE_YEAR}, e.g. {example}). This usually means it's a "
                    f"sample index (0, 0.01, 0.02, ...), not real calendar time. If that's intentional, "
                    f"call validate_input(..., timestamp_is_index=True) to acknowledge it explicitly."
                )

    if df[timestamp_col].duplicated().any():
        dupes = df[timestamp_col][df[timestamp_col].duplicated()].tolist()
        preview = dupes[:5]
        raise InputValidationError(
            f"Duplicate timestamps found: {preview}{' ...' if len(dupes) > 5 else ''}"
        )

    df = df.sort_values(timestamp_col).reset_index(drop=True)

    exclude_cols = {timestamp_col}
    if sensor_id_col is not None:
        if df[sensor_id_col].isna().any():
            raise InputValidationError(f"Missing sensor IDs found in column '{sensor_id_col}'")
        # v2.1 fix: normalise to a column literally named 'sensor_id', matching
        # the documented contract, instead of keeping the original column name.
        if sensor_id_col != "sensor_id":
            df = df.rename(columns={sensor_id_col: "sensor_id"})
        exclude_cols.add("sensor_id")

    if sensor_cols is None:
        sensor_cols = [c for c in df.columns if c not in exclude_cols]

    if not sensor_cols:
        raise InputValidationError("No sensor value columns found besides timestamp/sensor-id columns")

    missing_cols = [c for c in sensor_cols if c not in df.columns]
    if missing_cols:
        raise InputValidationError(f"Declared sensor columns not found in data: {missing_cols}")

    non_numeric = [c for c in sensor_cols if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise InputValidationError(f"Sensor column(s) are not numeric: {non_numeric}")

    nan_report = {c: int(df[c].isna().sum()) for c in sensor_cols if df[c].isna().any()}
    if nan_report:
        raise InputValidationError(f"Missing (NaN) values found in sensor columns: {nan_report}")

    if sensor_id is not None:
        df["sensor_id"] = sensor_id

    return df.set_index(timestamp_col)


if __name__ == "__main__":
    good = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="h"),
        "s1": [10.1, 10.3, 10.2, 50.9, 10.4],
        "s2": [5.0, 5.1, 5.0, 5.2, 5.1],
    })

    print("=== Test 1: valid input (no sensor id) ===")
    validated = validate_input(good)
    print(validated)
    print("PASSED\n")

    print("=== Test 2: valid input WITH sensor_id ===")
    validated2 = validate_input(good, sensor_id="temperature_sensor_01")
    print(validated2)
    print("PASSED\n")

    print("=== Test 3: min_rows enforcement (require 10, only have 5) ===")
    try:
        validate_input(good, min_rows=10)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}\n")

    print("=== Test 4: numeric index mistaken for real time (the Week 4 bug) ===")
    numeric_index_df = pd.DataFrame({
        "timestamp": [0, 0.01, 0.02, 0.03, 0.04],
        "s1": [1.0, 1.01, 1.02, 1.03, 1.04],
    })
    try:
        validate_input(numeric_index_df)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}\n")

    print("=== Test 5: same numeric index, now explicitly acknowledged ===")
    validated5 = validate_input(numeric_index_df, timestamp_is_index=True)
    print(validated5)
    print("PASSED (explicitly acknowledged as index, not real time)\n")

    print("=== Test 6: missing value still rejected (v1 behaviour preserved) ===")
    bad_missing = good.copy()
    bad_missing.loc[1, "s1"] = None
    try:
        validate_input(bad_missing)
        print("FAILED — should have raised InputValidationError")
    except InputValidationError as e:
        print(f"REJECTED correctly: {e}\n")

    print("=== Test 7: sensor_id_col normalises to a 'sensor_id' column (v2.1 fix) ===")
    with_device_col = good.copy()
    with_device_col["device_id"] = "sensor_A"
    validated7 = validate_input(with_device_col, sensor_id_col="device_id")
    print(validated7)
    assert "sensor_id" in validated7.columns, "FAILED: sensor_id column not present"
    assert "device_id" not in validated7.columns, "FAILED: original column name still present"
    print("PASSED (original 'device_id' column renamed to standard 'sensor_id')")
