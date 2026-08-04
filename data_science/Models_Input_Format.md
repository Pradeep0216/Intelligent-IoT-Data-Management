# Models Sub-Team — Required Input Format (v1)
**Owner:** Deepakkumar Govindan · Week 4

This is the shared input contract every detector must receive data in, enforced by `input_validator.py` before data reaches a detector.

## Required structure

| Field | Type | Rule |
|---|---|---|
| `timestamp` (or equivalent, e.g. `time`) | datetime (parseable) | Required column. Must be unique — no duplicate timestamps. Data is sorted by this column before use. |
| One or more sensor value columns (e.g. `s1`, `s2`, `temperature`) | numeric (int/float) | At least one required. No missing/NaN values allowed — reject, don't silently fill. |

## What the validator checks, in order

1. Input is a pandas DataFrame and is not empty.
2. The timestamp column exists (name is configurable via `timestamp_col`, default `timestamp`).
3. Timestamps parse as valid datetimes.
4. No duplicate timestamps.
5. At least one sensor column exists besides the timestamp column.
6. All sensor columns are numeric.
7. No NaN/missing values in any sensor column.

If any check fails, `validate_input()` raises `InputValidationError` with a specific message instead of letting bad data reach a detector and fail unpredictably later.

## Known limitation (found during real-data testing)

Tested against `datasets/complex.csv` (1008 rows) in this repo. The validator passed all rows, but that dataset's `time` column is a plain numeric index (0, 0.01, 0.02 ...), not real calendar time. `pd.to_datetime()` silently converts such numbers into nanosecond-offset dates from 1970-01-01 rather than raising an error. The validator confirms structural correctness (parseable, unique, sorted) but cannot currently distinguish a real timestamp from a numeric index that happens to parse. Flagging this for the team — may need an explicit real-timestamp check in v2.

## Usage

```python
from input_validator import validate_input, InputValidationError

try:
    clean_df = validate_input(raw_df, timestamp_col="time")  # column name is configurable
    # clean_df is now safe to pass into any detector
except InputValidationError as e:
    print(f"Rejected: {e}")
```

## Not yet handled (out of scope for v1, flag if needed for Week 5)

- Multi-sensor identification (`sensor_name` field) — current version assumes one dataset = one set of co-located sensors, not a mixed multi-device stream.
- Outlier/range checks (e.g. physically impossible sensor readings) — validator checks structure and completeness, not plausibility.
- Distinguishing real calendar timestamps from numeric time-indexes that happen to parse as datetimes (see limitation above).
- Timezone normalization — timestamps are parsed as-is; no explicit UTC conversion yet.
