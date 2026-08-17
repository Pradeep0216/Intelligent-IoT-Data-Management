# Correlation Alert Service:

## Overview:

The Correlation Alert Service detects changes in relationships between IoT data streams. It cleans input data, creates rolling windows, calculates correlation matrices, compares consecutive windows, and returns alerts.

The service accepts JSON data or an uploaded CSV file through a Flask API. Automated tests cover the data pipeline and API behaviour.

## Project structure:

1. `preprocessing.py` validates and cleans input data.
2. `correlation.py` creates windows, calculates correlations, compares changes, and generates alerts.
3. `serialization.py` converts pipeline results into API safe values.
4. `main.py` connects preprocessing with correlation analysis.
5. `server.py` provides the Flask API.
6. `requirements.txt` pins the required Python packages.
7. `tests/` contains the automated regression tests.

## Requirements:

Use Python 3.13. Run every command from the repository root.

## Installation:

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the pinned dependencies:

```bash
python -m pip install -r correlation_alert/requirements.txt
```

## Run the server:

Start the Flask service from the repository root:

```bash
python -m correlation_alert.server
```

The service listens on `http://127.0.0.1:5001`.

Keep this terminal open while testing the API.

## Check the service status:

Open a second terminal and run:

```bash
curl http://127.0.0.1:5001/service-status
```

A successful response contains:

```json
{
  "status": "running",
  "message": "Correlation Alert Service is running.",
  "service": "correlation-alert-api"
}
```

## Test the API with a CSV file:

The following request uses the shared real traffic dataset:

```bash
curl -X POST http://127.0.0.1:5001/detect-correlation-alert \
  -F "file=@datasets/nab_realtraffic/traffic_4stream_merged.csv" \
  -F "timestamp_col=timestamp" \
  -F "selected_streams=occupancy_t4013,speed_t4013,occupancy_6005,speed_6005" \
  -F "window_size=60" \
  -F "step_size=30" \
  -F "method=pearson" \
  -F "sampling_frequency=5min" \
  -F "missing_method=interpolate"
```

The response contains these main fields:

1. `summary` reports processed rows, windows, changes, alerts, and skipped pairs.
2. `data_quality` reports input cleaning counts.
3. `correlations` contains one correlation matrix for each window.
4. `changes` contains comparisons between consecutive windows.
5. `alerts` contains changes that reached an alert threshold.
6. `skipped_pairs` contains pairs with undefined correlations.

Invalid input returns HTTP 400 with `error_type` set to `invalid_input`.

## Run automated tests:

Run the full Correlation Alert test suite from the repository root:

```bash
python -m pytest correlation_alert/tests -q
```

A successful run finishes with no failed tests.

## Continuous integration:

The GitHub Actions workflow is stored in `.github/workflows/correlation-alert-tests.yml`.

It runs when Correlation Alert files or the workflow file change. It can also be started manually from GitHub Actions.

The workflow uses these commands:

```bash
python -m pip install -r correlation_alert/requirements.txt
python -m pytest correlation_alert/tests -q
```
