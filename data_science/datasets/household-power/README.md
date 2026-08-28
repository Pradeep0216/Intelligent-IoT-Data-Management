# Household Electric Power Consumption

**Branch:** `deepak/report/household-power`

## Source
UCI Machine Learning Repository — [Individual Household Electric Power Consumption](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption) (dataset ID 235). Public domain.

## What it is
Minute-level smart-meter readings from one household in Sceaux, France, Dec 2006 – Nov 2010 (~4 years, 2,075,259 raw readings). Variables: `Global_active_power, Global_reactive_power, Voltage, Global_intensity, Sub_metering_1/2/3`.

## Files
- `notebook.ipynb` — Task 1 dataset selection/relevance write-up + light preliminary exploration. Continues into Task 2 full analysis.
- `data/household_power_hourly.csv` — full 4-year series resampled to hourly averages (34,589 rows), for fast loading.
- `data/household_power_daily_missing.csv` — daily count of missing minutes, for gap analysis.

Raw minute-level source file (2M+ rows, ~130MB) was not committed — see notebook for the download link if the full-resolution data is needed.

## Why this dataset
Real (not synthetic) multi-channel IoT-style telemetry with genuine missing-data gaps and real consumption spikes — see notebook's "Dataset Selection and Relevance" section for full justification.
