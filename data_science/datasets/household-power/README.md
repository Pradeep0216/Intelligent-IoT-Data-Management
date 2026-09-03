# Household Electric Power Consumption — Models/AIntl Evaluation

**Branch:** `deepak/report/household-power` (experiment only — not merged into `main`)
**Location:** `data_science/datasets/household-power/`

## Source and provenance

- **Dataset:** Individual Household Electric Power Consumption, [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption) (dataset ID 235). Public domain.
- **What it is:** Minute-level smart-meter readings from one household in Sceaux, France, Dec 2006 – Nov 2010 (~4 years, 2,075,259 raw readings).
- **Transformations applied:**
  1. Resampled from minute-level to hourly averages (`household_power_hourly.csv`, 34,589 rows) — done in Task 1.
  2. For Task 2's pipeline runs: dropped 421 hourly rows (1.2%) with missing readings (the input validator has no imputation and rejects any row with a missing sensor value). This is the only transformation applied before feeding data to the pipeline.
  3. Timestamps formatted as ISO-8601 strings (`YYYY-MM-DDTHH:MM:SSZ`) to match what `analytics_integration.pipeline` and the Correlation service expect.
- **Assumptions:** `Global_active_power` was chosen as the anomaly-detection metric (most representative of overall load). `Global_active_power` vs `Voltage` was chosen as the correlation pair for the full pipeline run because, unlike `Global_active_power` vs `Global_intensity` (which are almost physically identical), it has a real, fluctuating relationship (load-dependent voltage sag) that gives the correlation detector something meaningful to evaluate.

## Files

- `notebook.ipynb` — full reproducible investigation: Task 1 dataset selection + Task 2 EDA, preprocessing, Models/AIntl execution, evaluation, visualisations, interpretation, limitations, conclusions. Runs top to bottom with no manual steps.
- `Household_Power_Models_AIntl_Evaluation_Report.pdf` — professional summary report of Task 2's findings, for stakeholder review.
- `data/household_power_hourly.csv` — full 4-year series resampled to hourly averages (34,589 rows).
- `data/household_power_daily_missing.csv` — daily count of missing minutes (from Task 1's gap analysis).

The raw minute-level source file (2M+ rows, ~130MB) was not committed. To regenerate it:
```bash
curl -O https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip
unzip "individual+household+electric+power+consumption.zip"
```

## How to reproduce

1. From the repo root, install dependencies (already in `requirements.txt`, plus a couple used only for this notebook's plots):
   ```bash
   pip install -r requirements.txt
   pip install matplotlib seaborn nbclient ipykernel
   python -m ipykernel install --user --name python3
   ```
2. From `data_science/datasets/household-power/`, run the notebook top to bottom:
   ```bash
   cd data_science/datasets/household-power
   jupyter nbconvert --to notebook --execute notebook.ipynb --output notebook.ipynb
   ```
   or open it in Jupyter/VS Code and run all cells. The notebook adds the repo root to `sys.path` itself, so it can import `data_science`, `analytics_integration`, `correlation_alert`, and `analytics_validation` directly — no extra setup needed.
3. To regenerate just the PDF report, see the report-generation approach documented inline at the top of `notebook.ipynb`'s Task 2 section (the same numbers/figures the report cites are produced by the notebook itself).

## What this experiment covers

Runs the existing AIntl path — `Dataset -> Models input validation -> Isolation Forest -> Models adapter -> Correlation path -> Correlation adapter -> Analytics response -> Draft V0.1 validation` — against this dataset, with no changes made to the Models, Correlation, or AIntl implementation code. See the PDF report or `notebook.ipynb` for full results, evaluation, limitations, and conclusions.
