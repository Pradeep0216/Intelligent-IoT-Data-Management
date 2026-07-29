import csv
from pathlib import Path


RESULTS_FILE = Path("CCA108_final_results.csv")
REPORT_FILE = Path("CCA108_window_method_test.md")


with RESULTS_FILE.open(
    "r",
    encoding="utf-8",
) as file:
    rows = list(csv.DictReader(file))


successful_rows = [
    row
    for row in rows
    if row["status"] == "SUCCESS"
]

failed_rows = [
    row
    for row in rows
    if row["status"].startswith("FAILED")
]


successful_runtimes = [
    float(row["average_runtime_ms"])
    for row in successful_rows
]

maximum_successful_runtime = max(successful_runtimes)

spearman_error = "No error recorded"

if failed_rows:
    spearman_error = failed_rows[0]["notes"]


table_lines = [
    "| Method | Window | Step | Status | Windows | Alerts | LOW | MEDIUM | HIGH | Average runtime |",
    "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
]

for row in rows:
    runtime_text = f"{row['average_runtime_ms']} ms"

    if row["status"].startswith("FAILED"):
        runtime_text += " — time to failure"

    table_lines.append(
        f"| {row['method']} "
        f"| {row['window_size']} "
        f"| {row['step_size']} "
        f"| {row['status']} "
        f"| {row['windows']} "
        f"| {row['alerts']} "
        f"| {row['low']} "
        f"| {row['medium']} "
        f"| {row['high']} "
        f"| {runtime_text} |"
    )


results_table = "\n".join(table_lines)


report = f"""# CCA108 — Rolling-Window Parameter and Correlation Method Evaluation

**Owner:** Vishnu Vardhan Reddy Pulluru
**Due date:** Sunday, 26 July 2026
**Project:** Intelligent IoT Data Management

## 1. Objective

The objective was to measure how correlation-alert output changes with different `window_size`, `step_size`, and correlation methods. The dataset, timestamp column, and selected streams were held constant so that the effect of the tested parameters could be compared fairly.

The purpose was to support an evidence-based default configuration rather than automatically retaining the values inherited from the T1 implementation.

## 2. Technical background

Pearson correlation measures linear relationships between variables. Spearman correlation measures monotonic relationships using ranked values.

The service divides the time series into overlapping rolling windows. Correlations are calculated within each window, and the delta between consecutive windows is used to identify changes in relationships between sensor streams.

## 3. Dataset and test environment

| Item | Value |
| Dataset | `datasets/complex.csv` |
| Dataset rows | 1008 |
| Timestamp column | `time` |
| Sensor streams | `s1`, `s2`, `s3` |
| Missing values | 0 |
| Window configurations | 20/10, 40/20, 60/30 |
| Methods requested | Pearson and Spearman |
| Runtime repetitions | 3 per configuration |
| API endpoint | `/detect-correlation-alert` |

The preprocessing logs confirmed that the dataset was sorted, converted to numeric form, cleaned, and validated successfully before correlation analysis.

## 4. Test configurations

The following configurations were tested while keeping the dataset and streams unchanged:

1. `window_size=20`, `step_size=10`
2. `window_size=40`, `step_size=20`
3. `window_size=60`, `step_size=30`

Each configuration was requested with both `pearson` and `spearman`.

## 5. Results

{results_table}

Spearman entries are reported as failed rather than as zero alerts because the API did not complete the correlation calculation.

## 6. Findings

### 6.1 Alert output

Pearson produced between 18 and 20 alerts across the three configurations. The 40/20 configuration produced the lowest total alert count, with 18 alerts.

The 20/10 configuration produced 19 alerts across 99 rolling windows. The 40/20 configuration produced 18 alerts across 49 windows. The 60/30 configuration produced 20 alerts across 32 windows.

This shows that reducing the number of windows did not produce a proportional reduction in alert volume.

### 6.2 Severity distribution

MEDIUM alerts were the largest severity category in every successful Pearson configuration.

The 40/20 configuration retained all three severity levels while producing the lowest overall alert count.

### 6.3 Spearman implementation failure

All three lowercase `spearman` requests reached preprocessing successfully but returned HTTP 500 during later processing.

The repeated error was:

`{spearman_error}`

Alternative spellings such as `Spearman`, `SPEARMAN`, and `spearmanr` were rejected as invalid method names. Therefore, lowercase `spearman` was the correct API value, but the inherited Spearman execution path failed internally.

### 6.4 Runtime and scalability

Each configuration was executed three times and the average request runtime was recorded.

The highest average runtime among successful configurations was {maximum_successful_runtime:.3f} ms. No noticeable runtime threshold was reached on this 1008-row, three-stream dataset.

The 20/10 configuration evaluated the greatest number of rolling windows and is therefore the configuration most likely to create higher processing cost as dataset size or stream count increases.

Spearman failure runtimes represent time to failure and must not be interpreted as successful Spearman processing performance.

### 6.5 Timestamp observation

The sequential integer values in the `time` column were interpreted as values close to the Unix epoch, producing timestamps around 1 January 1970. This does not affect the controlled parameter comparison but should be corrected before meaningful dashboard display.

## 7. Three-line recommendation

Use Pearson with `window_size=40` and `step_size=20` as the provisional default for the current dataset.
It produced the lowest alert total while retaining LOW, MEDIUM, and HIGH severity detection and reducing the rolling-window count from 99 to 49 compared with 20/10.
Retest the recommendation after the inherited Spearman defect is fixed and when a larger real IoT dataset becomes available.

## 8. Limitations

The evaluation used one simulated dataset containing 1008 rows and three sensor streams. Spearman could not be compared successfully because all Spearman requests returned HTTP 500. Runtime behaviour may change significantly with larger datasets, smaller step sizes, or additional sensor streams.

## 9. Evidence files

- `CCA108_final_results.csv`
- `CCA108_runtime_runs.csv`
- `CCA108_benchmark_console.txt`
- Raw API responses in `cca108_raw_evidence/`
"""


REPORT_FILE.write_text(
    report,
    encoding="utf-8",
)

print(f"Created {REPORT_FILE}")
