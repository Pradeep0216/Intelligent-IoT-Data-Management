# Smart Farming (ThingSpeak Channel 80502): Models/AIntl Evaluation

**Branch:** `kim/report/farming` (experiment only, not merged into `main`)
**Location:** `data_science/datasets/farming/`

## Source and provenance

- **Dataset:** ThingSpeak public channel [80502](https://thingspeak.com/channels/80502) (MathWorks ThingSpeak IoT platform), a public greenhouse climate-monitoring feed. Retrieved via the public `feeds.csv` endpoint (`https://api.thingspeak.com/channels/80502/feeds.csv?results=8000`), no API key required.
- **What it is:** climate-computer readings from inside a greenhouse, logged roughly once a minute: air temperature, a second temperature probe, relative humidity, and CO2, plus four values (wet-bulb temperature, absolute humidity, dew point, humidity deficit) the device computes from the first two and reports alongside them. Coverage is 27 June to 12 October 2019, arriving as three disjoint export blocks separated by two multi-week outages (47 and 55 days).
- **Transformations applied:**
  1. **Field identification (Task 1).** ThingSpeak exports only `field1` through `field8` with no labels. The mapping used here (`temp_c`, `wet_bulb_c`, `temp2_c`, `humidity_pct`, `abs_humidity_gm3`, `dew_point_c`, `humidity_deficit_gm3`, `co2_ppm`) was derived from the data itself, not assumed: the four derived fields were recomputed from `temp_c`/`humidity_pct` using published psychrometric formulas (Tetens saturation vapour pressure, Magnus dew point, Stull wet-bulb approximation) and matched to the file to within its 0.1 rounding resolution.
  2. **Fault-sentinel removal (Task 2).** 22 rows (0.29% of the file) encode sensor failure as fixed error-code values (`99.9` / `455` / `9999` / `0.0`) rather than `NaN`, and were removed explicitly, since the input validator does not catch this (see "Evidence: what the input validator actually catches" below).
  3. **Block selection (Task 2).** Selected the single longest continuous export block (7 to 12 Oct 2019, 7,261 rows at ~60s cadence) as the working series, to keep the two multi-week outages out of the rolling-correlation windows.
  4. Timestamps formatted as ISO-8601 strings (`YYYY-MM-DDTHH:MM:SSZ`) to match what `analytics_integration.pipeline` expects.
- **Assumptions:** `temp_c` (air temperature) was chosen as the Models anomaly-detection metric. `temp_c` vs `humidity_pct` was chosen as the primary Correlation pair because the two are physically forced to move in opposite directions (a known-sign relationship to test the module against); `temp_c` vs `co2_ppm` was run as a deliberately weaker second pair, since the CO2 channel sits at its ~400ppm outdoor-baseline floor for most of the record. The four derived fields (`wet_bulb_c`, `abs_humidity_gm3`, `dew_point_c`, `humidity_deficit_gm3`) were excluded from correlation analysis, since they are deterministic functions of `temp_c`/`humidity_pct`, not independent sensor readings, so correlating them would just measure the formula.

## Files

- `notebook.ipynb`: the full reproducible investigation. Task 1 (dataset selection, field identification, timestamp/quality checks, correlation suitability) plus Task 2 (EDA, preprocessing, Models/AIntl execution, evaluation, visualisations, interpretation, limitations, conclusions). Runs top to bottom with no manual steps; every cell's output is already saved inside it.
- `Smart_Farming_Models_AIntl_Evaluation_Report.pdf`: the professional summary report of Task 2's findings, for stakeholder/project review.
- `make_report.py`: regenerates the PDF from `outputs/task2_results.json` and `outputs/*.png` (both produced by the notebook).
- `quick_check.py`: a plain, runnable script that reproduces the preprocessing and one full-pipeline call, without needing the notebook or Jupyter. Run with `python data_science/datasets/farming/quick_check.py` from anywhere.
- `show_alerts.py`: prints the actual individual detections (timestamps, values, scores, correlation windows), not just summary counts. Run with `python data_science/datasets/farming/show_alerts.py`.
- `run_checks.py`: runs every specific evaluation check described in the Findings section as one script: detector alone, correlation alone (both pairs), the full combined pipeline, the independent-outlier cross-check, the determinism check, and all four input-validator behaviour tests (missing columns, duplicate timestamps, NaN values, fault-sentinel values). Run with `python data_science/datasets/farming/run_checks.py`.
- `data/farming.csv`: the raw ThingSpeak export (7,488 rows x 10 columns), unmodified.
- `outputs/`: the results this experiment produced. `task2_results.json` (all headline numbers) and 7 charts (`.png`) covering the EDA distributions, flagged anomalies over time and by hour/date, rolling correlation, correlation severity, and runtime scaling. This is the evidence record the findings below and the PDF report are built from.

## What this experiment covers

Ran the existing AIntl path (`Dataset -> Models input validation -> Isolation Forest -> Models adapter -> Correlation path -> Correlation adapter -> Analytics response -> Draft V0.1 validation`) against this dataset, with no changes made to the Models, Correlation, or AIntl implementation code.

Configuration used throughout:

| Parameter | Value |
|---|---|
| `entity_id` | `greenhouse_ch80502` |
| `model_metric` | `temp_c` |
| `correlation_streams` | `[temp_c, humidity_pct]` and `[temp_c, co2_ppm]` |
| `detector_name` | `isolationforest` |
| `detector_parameters` | `{"contamination": 0.05}` |
| `correlation_window_size` / `step_size` | `20` / `10` |
| `correlation_method` | `pearson` |

## Findings

**Data integrity.** 7,488 raw readings, zero duplicates, zero `NaN`s, but 22 rows (0.29%) encode sensor failure as fixed error-code values (`99.9`/`455`/`9999`/`0.0`), invisible to any missing-value check. The input validator correctly rejects unmapped columns, duplicate timestamps, and `NaN` sensor values, but does **not** catch these fault sentinels, since they are valid non-null floats. That's a gap in the validator's contract, not a defect in this run.

**Models path, Isolation Forest on `temp_c`.** Flagged 357/7,261 readings (4.92%), concentrated on 4 of 5 calendar days (2 days received zero flags), lining up with a real multi-hour heat spike (9 Oct, to 29.1°C) and a separate cold dip (10 Oct), not the recurring day/night cycle. 100% of independently-identified top/bottom 0.5th-percentile readings were also flagged, and repeated runs were bit-for-bit deterministic. See `outputs/anomaly_timeseries.png` and `outputs/anomaly_hour_of_day.png`.

**Correlation path, two experiments, an unexpected result.** `temp_c` vs `humidity_pct` (the genuinely physically-linked pair, negative correlation expected) produced 178 alerts (46 HIGH). `temp_c` vs `co2_ppm` (deliberately the *weaker* pair, since CO2 sits at its ~400ppm floor) produced **more**: 258 alerts (108 HIGH). Cause: a near-constant channel makes rolling Pearson correlation numerically unstable (a few ppm of jitter swings it between +1 and -1), which the Correlation module currently reports identically to a genuine relationship change. See `outputs/correlation_rolling.png` and `outputs/correlation_severity.png`.

**Full pipeline.** Ran end-to-end with no code changes, 535 total alerts (357 point anomalies + 178 correlation-change), completed in 1.31s for the full 7,261-row block, scaling close to linearly with row count (`outputs/runtime_scalability.png`).

**No ground-truth labels exist for this dataset**, so no precision/recall/F1/AUC is reported, per the evaluation brief. The findings above rely on independent statistical cross-checks, determinism, and domain plausibility instead.

## Limitations

- The input validator does not recognise domain-specific fault sentinels, only literal `NaN`.
- Neither the validator nor the correlation window is gap-aware (a window is row-count-based, not time-based); this dataset's two multi-week outages were excluded by hand for that reason.
- The Correlation module cannot distinguish real drift from noise-driven instability in a near-constant channel, as demonstrated directly by the co2 experiment above.
- `temp2_c`'s physical location is undocumented; single device, single 5-day working block; Models path exercised univariately only.

## How to reproduce

This repo's `.venv` (Python 3.9) cannot run `analytics_integration.pipeline`, because `correlation_alert/settings.py` uses `str | None` type-hint syntax, which requires **Python 3.10+**. Set up a separate environment:

```bash
# From the repo root
python3.12 -m venv .venv312          # any Python 3.10+ works
source .venv312/bin/activate
pip install pandas numpy matplotlib seaborn scikit-learn flask flask-cors requests \
            nbclient nbconvert ipykernel reportlab Pillow
python -m ipykernel install --user --name farming312 --display-name "farming312"
```

**Full investigation (recommended):** run the notebook top to bottom.

```bash
cd data_science/datasets/farming
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=farming312 \
    notebook.ipynb --output notebook.ipynb
```

or open it in Jupyter/VS Code (select the `farming312` kernel) and run all cells. It adds the repo root to `sys.path` itself, so it imports `data_science`, `analytics_integration`, and `correlation_alert` directly. To regenerate just the PDF afterwards, run `python make_report.py`.

**Quick check (no notebook needed):** `quick_check.py` runs the same preprocessing and full-pipeline call as a plain script. Run it from anywhere, once the environment above is set up:

```bash
python data_science/datasets/farming/quick_check.py
```

Expected output ends with `Pipeline summary: {'processed_items': 7261, 'alert_count': 535}`, matching the numbers in the Findings section above. Edit the `correlation_streams` argument inside the script to `["temp_c", "co2_ppm"]` to reproduce the second correlation experiment instead.
