Correlation API Contract Draft

Project: Intelligent IoT Data Management Prepared by: Thirupathaiah
Miriyala Task: Correlation Change Alert API Documentation Date: 25 July
2026

## 1. Objective

The purpose of this document is to describe the JSON response returned
by the Correlation Alert API after a successful POST request to
/detect-correlation-alert. It documents the request parameters, response
structure, field meanings, and integration considerations for the
Analytics Integration team.

## 2. API Endpoint

  -----------------------------------------------------------------------
  Item                                Value
  ----------------------------------- -----------------------------------
  Method                              POST

  Endpoint                            /detect-correlation-alert

  Purpose                             Processes uploaded CSV sensor data
                                      and detects significant correlation
                                      changes.
  -----------------------------------------------------------------------

## 3. Request Parameters

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| file | CSV File | simple.csv | CSV dataset uploaded for processing. |
| selected_streams | String | s1,s2,s3 | Sensor streams to analyse. |
| window_size | Integer | 20 | Sliding window size used for correlation calculation. |
| step_size | Integer | 10 | Sliding window step size. |
| method | String | pearson | Correlation method used. |
| timestamp_col | String | time | Name of the timestamp column in the uploaded dataset. |

## 4. Response Structure

Top-level JSON response fields returned by the API are:

- status
- correlations
- alerts
- changes
- summary

| Field | Type | Example | Meaning |
|------|------|---------|---------|
| status | String | success | Indicates request completed successfully. |
| correlations | Array | [{...}] | Correlation results for each sliding window. |
| alerts | Array | [{...}] | Detected correlation alerts. |
| changes | Array | [{...}] | Correlation changes calculated for sliding windows. |
| summary | Object | {...} | Overall processing statistics. |

---

## 5. Changes Object
Each item in the `changes` array contains the following fields.

| Field | Type | Description |
|------|------|-------------|
| window_index | Integer | Sliding window index where the correlation change was detected. |
| start_time | String | Start timestamp of the sliding window. |
| end_time | String | End timestamp of the sliding window. |
| stream_1 | String | First sensor stream. |
| stream_2 | String | Second sensor stream. |
| previous_corr | Float | Correlation value before the detected change. |
| current_corr | Float | Correlation value after the detected change. |
| delta | Float | Absolute difference between previous and current correlation values. |

---

## 6. Alerts Object
Each item in the `alerts` array contains the following fields.

| Field | Type | Description |
|------|------|-------------|
| window_index | Integer | Sliding window index. |
| start_time | String | Start timestamp of the sliding window. |
| end_time | String | End timestamp of the sliding window. |
| stream_1 | String | First sensor stream. |
| stream_2 | String | Second sensor stream. |
| previous_corr | Float | Previous correlation value. |
| current_corr | Float | Current correlation value. |
| delta | Float | Correlation difference. |
| alert_level | String | Alert severity (LOW, MEDIUM, HIGH). |
| reason | String | Explanation describing why the alert was generated. |

---

## 7. Correlation Configuration
The API currently supports the following configuration parameters.

| Parameter | Description |
|----------|-------------|
| method | Correlation method used for calculation. Current implementation supports **pearson**. |
| window_size | Number of records included in each sliding window. |
| step_size | Number of records the sliding window advances between calculations. |

---

## 8. Supported Severity Values
Current implementation supports the following alert severity levels.

| Severity | Description |
|---------|-------------|
| LOW | Small but significant correlation change. |
| MEDIUM | Moderate correlation change or strong-to-weak / weak-to-strong transition. |
| HIGH | Large correlation change requiring immediate attention. |

---

## 9. Required and Optional Fields
### Required Request Parameters

- file
- timestamp_col
- selected_streams

### Optional Request Parameters

- window_size (default value applied if omitted)
- step_size (default value applied if omitted)
- method (defaults to pearson)

### Optional Response Fields

- start_time
- end_time

These fields are generated when timestamp information is available in the uploaded dataset.

---

## 10. Error Response
Example error response:

```json
{
  "status": "error",
  "message": "Missing 'timestamp_col'."
}
```

Possible causes include:

- Missing timestamp_col
- Missing selected_streams
- Missing uploaded dataset
- Unexpected server error

## 11. API Testing Evidence

The Correlation Alert API was tested locally after setting up the
project environment. Both required endpoints were executed successfully
using the provided Postman collection. The GET request confirmed that
the service was running correctly, while the POST request successfully
processed the sample CSV dataset and returned correlation analysis
results.

### Figure 1. Successful GET /service-status request

![GET Service Status](evidence/postman_get_service_status.png)

### Figure 2. Successful POST /detect-correlation-alert request

![POST Detect Correlation Alert](evidence/postman_post_detect_correlation_alert.png)

### Figure 3. Flask Server Terminal

![Flask Server Terminal](evidence/flask_server_terminal.png)

## 12. Alert Object Fields

  Field           Type      Example                  Description
  --------------- --------- ------------------------ ---------------------------------------
  alert_level     String    HIGH                     Severity of alert
  stream_1        String    s1                       First sensor stream
  stream_2        String    s2                       Second sensor stream
  previous_corr   Number    -0.9466                  Previous correlation value
  current_corr    Number    0.6852                   Current correlation value
  delta           Number    1.6319                   Difference between correlation values
  window_index    Integer   15                       Sliding window index
  start_time      String    Timestamp                Window start time
  end_time        String    Timestamp                Window end time
  reason          String    Correlation changed...   Reason for alert

## 13. Summary Object

  Field                 Observed Value
  --------------------- ----------------
  alerts                16
  changes               294
  processed_rows        1008
  windows               99
  correlation_results   99

## 14. Sample JSON Response (Excerpt)

{ "status": "success", "summary": { "alerts": 16, "changes": 294,
"correlation_results": 99, "processed_rows": 1008, "windows": 99 } }

## 15. Integration Notes

Verify the status field before processing results.

Alerts contains significant correlation events.

Changes contains calculated correlation changes.

Summary provides overall processing statistics.

Client applications should handle empty alerts arrays gracefully.

## 16. Questions for Analytics Integration Team

Should every alert include a unique alert_id?

Why are start_time and end_time shown as placeholder timestamps in the
current response?

What is the intended difference between correlation_results and windows?

Should error responses follow a standard JSON schema?

## 17. Setup Issues & Fix

Issue: While testing the POST /detect-correlation-alert endpoint in
Postman, the request initially returned HTTP 415 Unsupported Media Type
and HTTP 500 Internal Server Error.

Cause: The CSV file was not uploaded correctly because the file field in
the Postman form-data request was configured incorrectly.

Fix: The file field was changed to the File type, simple.csv was
uploaded correctly, and the request was sent again. The API then
processed the dataset successfully and returned HTTP 200 OK.
