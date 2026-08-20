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

## Runtime

The detector runner also returns `runtime`. It is not currently copied into
every standard output record because runtime describes the overall detector
execution rather than one individual timestamp.

## Testing

The adapter was tested locally against the current Isolation Forest detector
runner branch.

It successfully produced:
- one normal standard JSON result
- one anomaly standard JSON result