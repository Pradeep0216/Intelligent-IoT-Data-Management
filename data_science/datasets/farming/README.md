# Smart Farming (ThingSpeak Channel 80502) — Models/AIntl Evaluation

**Branch:** `kim/report/farming` (experiment only — not merged into `main`)
**Location:** `data_science/datasets/farming/`

## Source and provenance

- **Dataset:** ThingSpeak public channel [80502](https://thingspeak.com/channels/80502) (MathWorks ThingSpeak IoT platform), a public greenhouse climate-monitoring feed. Retrieved via the public `feeds.csv` endpoint (`https://api.thingspeak.com/channels/80502/feeds.csv?results=8000`), no API key required.
- **What it is:** climate-computer readings from inside a greenhouse, logged roughly once a minute: air temperature, a second temperature probe, relative humidity, and CO2, plus four values (wet-bulb temperature, absolute humidity, dew point, humidity deficit) the device computes from the first two and reports alongside them. Coverage is 27 June – 12 October 2019, arriving as three disjoint export blocks separated by two multi-week outages (47 and 55 days).
- **Transformations applied:**
  1. **Field identification (Task 1).** ThingSpeak exports only `field1`…`field8` with no labels. The mapping used here (`temp_c`, `wet_bulb_c`, `temp2_c`, `humidity_pct`, `abs_humidity_gm3`, `dew_point_c`, `humidity_deficit_gm3`, `co2_ppm`) was derived from the data itself, not assumed: the four derived fields were recomputed from `temp_c`/`humidity_pct` using published psychrometric formulas (Tetens saturation vapour pressure, Magnus dew point, Stull wet-bulb approximation) and matched to the file to within its 0.1 rounding resolution.
  2. **Fault-sentinel removal (Task 2).** 22 rows (0.29% of the file) encode sensor failure as fixed error-code values (`99.9` / `455` / `9999` / `0.0`) rather than `NaN` — removed explicitly, since the input validator does not catch this (see notebook §"Evidence: what the input validator actually catches").
  3. **Block selection (Task 2).** Selected the single longest continuous export block (7–12 Oct 2019, 7,261 rows at ~60s cadence) as the working series, to keep the two multi-week outages out of the rolling-correlation windows.
  4. Timestamps formatted as ISO-8601 strings (`YYYY-MM-DDTHH:MM:SSZ`) to match what `analytics_integration.pipeline` expects.
- **Assumptions:** `temp_c` (air temperature) was chosen as the Models anomaly-detection metric. `temp_c` vs `humidity_pct` was chosen as the primary Correlation pair because the two are physically forced to move in opposite directions (a known-sign relationship to test the module against); `temp_c` vs `co2_ppm` was run as a deliberately weaker second pair, since the CO2 channel sits at its ~400ppm outdoor-baseline floor for most of the record. The four derived fields (`wet_bulb_c`, `abs_humidity_gm3`, `dew_point_c`, `humidity_deficit_gm3`) were excluded from correlation analysis — they are deterministic functions of `temp_c`/`humidity_pct`, not independent sensor readings, so correlating them would just measure the formula.

## Files

- `notebook.ipynb` — full reproducible investigation: Task 1 (dataset selection, field identification, timestamp/quality checks, correlation suitability) + Task 2 (EDA, preprocessing, Models/AIntl execution, evaluation, visualisations, interpretation, limitations, conclusions). Runs top to bottom with no manual steps.
- `Smart_Farming_Models_AIntl_Evaluation_Report.pdf` — professional summary report of Task 2's findings, for stakeholder review.
- `make_report.py` — regenerates the PDF report from `outputs/task2_results.json` and `outputs/*.png` (both produced by the notebook).
- `data/farming.csv` — the raw ThingSpeak export (7,488 rows × 10 columns), unmodified.
- `outputs/` — figures (`.png`) and the results summary (`task2_results.json`) produced by running the notebook; regenerated each time the notebook is re-executed.

## How to reproduce

This repo's `.venv` (Python 3.9) cannot run `analytics_integration.pipeline` — `correlation_alert/settings.py` uses `str | None` type-hint syntax, which requires **Python 3.10+**. Create a separate environment for this notebook:

```bash
# From the repo root
python3.12 -m venv .venv312          # any Python 3.10+ works
source .venv312/bin/activate
pip install pandas numpy matplotlib seaborn scikit-learn flask flask-cors requests \
            nbclient nbconvert ipykernel reportlab Pillow
python -m ipykernel install --user --name farming312 --display-name "farming312"
```

Then, from `data_science/datasets/farming/`, run the notebook top to bottom:

```bash
cd data_science/datasets/farming
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=farming312 \
    notebook.ipynb --output notebook.ipynb
```

or open it in Jupyter/VS Code (selecting the `farming312` kernel) and run all cells. The notebook adds the repo root to `sys.path` itself, so it can import `data_science`, `analytics_integration`, and `correlation_alert` directly — no extra setup needed beyond the environment above.

To regenerate just the PDF report (after the notebook has produced `outputs/task2_results.json` and the figures):

```bash
python make_report.py
```

## What this experiment covers

Runs the existing AIntl path — `Dataset -> Models input validation -> Isolation Forest -> Models adapter -> Correlation path -> Correlation adapter -> Analytics response -> Draft V0.1 validation` — against this dataset, with no changes made to the Models, Correlation, or AIntl implementation code. See the PDF report or `notebook.ipynb` for full results, evaluation, limitations, and conclusions.

**Headline results** (7,261-row primary block): Isolation Forest flagged 4.92% of `temp_c` readings, concentrated on two real excursions (a heat spike and a cold dip) rather than the recurring daily cycle, and was 100% deterministic. The Correlation module produced more, and more severe, alerts for the deliberately *weaker* pair (`temp_c` vs `co2_ppm`, 258 alerts) than for the genuinely physically-linked pair (`temp_c` vs `humidity_pct`, 178 alerts) — because a near-constant, floored channel makes rolling Pearson correlation numerically unstable, a failure mode the module does not currently distinguish from a real relationship change. The full pipeline, including Draft V0.1 response validation, completed in 1.3s for the full block with no ground-truth labels available (so no precision/recall/F1/AUC is reported, per the evaluation brief).
