import pandas as pd
import numpy as np


class InputValidationError(ValueError):
    """Raised when the caller's input is invalid (bad columns, unusable data).

    Kept separate from internal errors so the API can answer 400 instead of 500.
    """
    pass

def load_sensor_data(filepath: str = "datasets/complex.csv") -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    if "time" not in df.columns:
        raise ValueError("The dataset must contain a 'time' column.")

    print(f"[LOAD] Loaded {len(df)} rows")
    print(f"[LOAD] Columns: {list(df.columns)}")
    return df


def fix_timestamps(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    """Clean and sort the time column.

    Accepts numeric counters (datasets/complex.csv), ISO 8601 strings (the
    NAB datasets) and ThingSpeak created_at values ending in Z. The previous
    version forced pd.to_numeric, so any non numeric timestamp became NaN,
    every row was dropped, and validate_output still reported the empty
    result as clean and ready. Tests in testing/test_preprocess_timestamps.py.

    Both readings are attempted and the datetime one only wins when it parses
    strictly more rows. A plain row counter parses as epoch nanoseconds, so a
    tie means the column is a counter. Datetimes are normalised to UTC and the
    timezone is dropped, so the pipeline never compares aware against naive.
    """
    df = df.copy()
    total_rows = len(df)
    original = df[time_col]

    # CCA112 fix (CCA109 Defect 1): try datetime parsing first, fall back to
    # numeric. Previously this column was always coerced with pd.to_numeric,
    # so every datetime string became NaN and every row was dropped.
    parsed_datetime = pd.to_datetime(original, errors="coerce", utc=True, format="mixed")
    if parsed_datetime.notna().any():
        parsed_datetime = parsed_datetime.dt.tz_convert("UTC").dt.tz_localize(None)
    datetime_valid = int(parsed_datetime.notna().sum())

    parsed_numeric = pd.to_numeric(original, errors="coerce")
    numeric_valid = int(parsed_numeric.notna().sum())

    # Strictly greater. A plain row counter parses as epoch nanoseconds, so every
    # row is "valid" as a date and a tie would send a counter down the datetime
    # branch. On a tie the counter reading is the correct one.
    if datetime_valid > 0 and datetime_valid > numeric_valid:
        df[time_col] = parsed_datetime
        detected, valid = "datetime", datetime_valid
    else:
        df[time_col] = parsed_numeric
        detected, valid = "numeric", numeric_valid

    print(f"[TIMESTAMPS] Parsed '{time_col}' as {detected} "
          f"({valid}/{total_rows} rows valid)")

    invalid_time = int(df[time_col].isna().sum())
    if invalid_time > 0:
        print(f"[TIMESTAMPS] Removed {invalid_time} rows with invalid time values")

    df = df.dropna(subset=[time_col])

    duplicate_count = int(df.duplicated(subset=[time_col]).sum())
    if duplicate_count > 0:
        print(f"[TIMESTAMPS] Removed {duplicate_count} duplicate timestamps "
              f"(keeping first occurrence)")

    df = df.drop_duplicates(subset=[time_col])
    df = df.sort_values(by=time_col).reset_index(drop=True)

    # CCA112 fix (CCA109 Defect 2): an empty result is an error, not success.
    # InputValidationError so server.py answers 400 rather than 500.
    if len(df) == 0:
        raise InputValidationError(
            f"No usable timestamps left in column '{time_col}'. All {total_rows} "
            f"rows were removed. Detected format: {detected}. Check that the column "
            "holds numeric counters, ISO 8601 strings, or ThingSpeak created_at values."
        )

    print(f"[TIMESTAMPS] Sorted by '{time_col}', "
          f"detected {detected}, kept {len(df)} rows")
    return df


def convert_sensor_columns_to_numeric(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    df = df.copy()
    sensor_cols = [col for col in df.columns if col != time_col]

    # CCA112 fix (CCA109 Defect 4): count text values coerced to NaN so they are
    # reported separately from values that were genuinely missing on arrival.
    coerced_total = 0
    coerced_by_col = {}

    for col in sensor_cols:
        before_na = int(df[col].isna().sum())
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_na = int(df[col].isna().sum())

        coerced = after_na - before_na
        if coerced > 0:
            coerced_by_col[col] = coerced
            coerced_total += coerced

    print(f"[NUMERIC] Converted sensor columns to numeric: {sensor_cols}")
    if coerced_total > 0:
        print(f"[NUMERIC] Coerced {coerced_total} non-numeric value(s) to NaN: "
              f"{coerced_by_col}")

    df.attrs["non_numeric_coerced"] = coerced_total
    df.attrs["non_numeric_by_column"] = coerced_by_col
    return df

def handle_missing_values(df: pd.DataFrame, method: str = "interpolate") -> pd.DataFrame:
    df = df.copy()
    missing_before = df.isnull().sum().sum()

    if method == "interpolate":
        df = df.interpolate(method="linear", limit_direction="both")
    elif method == "ffill":
        df = df.ffill().bfill()
    elif method == "drop":
        df = df.dropna()
    else:
        raise ValueError(f"Unknown method: {method}")

    missing_after = df.isnull().sum().sum()
    print(f"[MISSING] Missing values before: {missing_before}")
    print(f"[MISSING] Missing values after: {missing_after}")
    return df


def remove_outliers(df: pd.DataFrame, sensor_cols: list, iqr_factor: float = 3.0) -> pd.DataFrame:
    df = df.copy()
    total_outliers = 0

    for col in sensor_cols:
        if df[col].isna().all():
            continue

        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower_bound = q1 - iqr_factor * iqr
        upper_bound = q3 + iqr_factor * iqr

        outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
        outlier_count = outlier_mask.sum()

        if outlier_count > 0:
            df.loc[outlier_mask, col] = np.nan
            total_outliers += outlier_count

    df[sensor_cols] = df[sensor_cols].interpolate(method="linear", limit_direction="both")

    print(f"[OUTLIERS] Replaced {total_outliers} outlier values")
    return df


def align_to_common_index(df: pd.DataFrame, time_col: str = "time", freq=1) -> pd.DataFrame:
    """Resample onto a regular grid.

    Handles both shapes fix_timestamps produces: numeric counters, where freq
    is an integer step, and datetimes, where freq is an offset string such as
    "5min".
    """
    df = df.copy()
    df = df.set_index(time_col)

    if pd.api.types.is_datetime64_any_dtype(df.index):
        if isinstance(freq, int):
            freq = "5min"
            print(
                "[ALIGN] Datetime index with an integer freq. Falling back to "
                "'5min', which matches the NAB realTraffic sampling rate. Pass "
                "an offset string such as '1min' for a differently sampled feed."
            )
        full_time_index = pd.date_range(
            start=df.index.min(), end=df.index.max(), freq=freq
        )
    else:
        start_time = int(df.index.min())
        end_time = int(df.index.max())
        full_time_index = range(start_time, end_time + 1, int(freq))

    df = df.reindex(full_time_index)

    df = df.interpolate(method="linear", limit_direction="both")
    df = df.reset_index().rename(columns={"index": time_col})

    print(f"[ALIGN] Reindexed time from {df[time_col].min()} to {df[time_col].max()} with freq={freq}")
    print(f"[ALIGN] Output rows after alignment: {len(df)}")
    return df


def validate_output(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    df = df.copy()

    if not df[time_col].is_monotonic_increasing:
        raise ValueError("Time column is not sorted in increasing order.")

    if df.isnull().sum().sum() != 0:
        raise ValueError("Data still contains missing values after preprocessing.")

    sensor_cols = [col for col in df.columns if col != time_col]
    for col in sensor_cols:
        df[col] = df[col].astype(np.float64)

    print(f"[VALIDATE] Output shape: {df.shape}")
    print("[VALIDATE] Dataset is sorted, clean, and ready for correlation analysis")
    return df


def run_pipeline(
    input_path: str = "datasets/complex.csv",
    output_path: str = "datasets/clean_sensor_data.csv"
) -> pd.DataFrame:
    print("=" * 60)
    print("SENSOR DATA PREPROCESSING PIPELINE")
    print("=" * 60)

    df = load_sensor_data(input_path)
    df = fix_timestamps(df, time_col="time")
    df = convert_sensor_columns_to_numeric(df, time_col="time")
    df = handle_missing_values(df, method="interpolate")

    sensor_cols = [col for col in df.columns if col != "time"]
    print(f"[INFO] Sensor columns: {sensor_cols}")

    df = remove_outliers(df, sensor_cols=sensor_cols, iqr_factor=3.0)
    df = align_to_common_index(df, time_col="time", freq=1)
    df = validate_output(df, time_col="time")

    df.to_csv(output_path, index=False)
    print(f"[DONE] Cleaned data saved to: {output_path}")
    print("=" * 60)

    return df


if __name__ == "__main__":
    clean_df = run_pipeline()
    print(clean_df.head())