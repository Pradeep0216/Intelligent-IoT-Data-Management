# Isolation Forest Standard JSON Output Adapter

## Purpose

This adapter converts the output produced by the standard detector runner
for Isolation Forest into the proposed standard Models JSON structure.

## Required fields

- timestamp
- sensor_id
- alert_type
- method
- anomaly_flag
- score

## Optional fields

- severity
- message
- supporting_values

## Field mapping

| Runner field | Standard output field | Notes |
|---|---|---|
| timestamp | timestamp | Converted to string/ISO format |
| input/context | sensor_id | Supplied to the adapter |
| anomaly_flag | alert_type | Used to derive normal or anomaly |
| model_name | method | Direct mapping |
| anomaly_flag | anomaly_flag | Direct mapping |
| score | score | Direct mapping |
| anomaly_flag | severity | Temporary logic |
| model_name + sensor_id | message | Human-readable message |
| input DataFrame row | supporting_values | Values for the matching timestamp |

## Temporary severity logic

Current prototype logic:

- Normal result -> `normal`
- Detected anomaly -> `high`

This is temporary logic only and has not been calibrated for production use.

## Integration role

This adapter is the Models-side detector-specific output adapter for
Isolation Forest.

The Models workflow is:

Input Validator
-> Detector Runner
-> Isolation Forest
-> Isolation Forest Output Adapter
-> Shared Models Output Adapter
-> Analytics Integration / API layer

The Isolation Forest adapter converts detector results into clear
timestamp-level records.

The shared `models_output_adapter.py` is the integration-facing adapter
that converts Models results into the Draft V0.1 alert structure used by
downstream Analytics Integration.

Therefore, this adapter does not replace the Analytics Integration adapter
or the shared Models adapter.

## Week 5 runtime and parameter handling

The detector runner provides `runtime` for the complete detector execution.

The current shared `models_output_adapter.py` preserves this as:

`supporting_values.runtime_ms`

Runtime is therefore not duplicated by this detector-specific adapter.

Isolation Forest parameters such as:

- contamination
- n_estimators
- random_state

are detector-level configuration values rather than timestamp-level values.

These parameters should be preserved as model-level metadata in the shared
Models output rather than repeated in every timestamp record.

## Evidence

The adapter includes two example outputs:

- `data_science/examples/isolation_forest_normal_output.json`
- `data_science/examples/isolation_forest_anomaly_output.json`

The normal example demonstrates a non-anomaly result.

The anomaly example demonstrates a detected anomaly with score, severity,
message and supporting sensor values.

## Testing

The adapter was tested against the Isolation Forest detector runner.

It successfully produced:

- one normal standard JSON result
- one anomaly standard JSON result