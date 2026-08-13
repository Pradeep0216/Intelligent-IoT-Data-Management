# Correlation Change Alert — Operational Runbook

**Owner:** Guna Varshith Kanagala
**Ticket:** CCA121
**Applies to:** `correlation_alert/` Flask service

This runbook is written for whoever is running the service during a demo or after
deployment, not for the person who wrote it. It covers how to start the service,
how to tell whether it is actually working, how to read its logs, and what to do
about the failures that have actually happened so far.

---

## 1. What this service does

It reads time-series sensor data, computes correlation between selected streams
over rolling windows, and raises an alert when the correlation between a pair of
streams changes by more than a threshold between consecutive windows.

Two endpoints:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/service-status` | GET | Health and readiness |
| `/detect-correlation-alert` | POST | Run the analysis |

---

## 2. Configuration

Every setting is an environment variable with a working default, so the service
starts with no configuration at all. Nothing here is a secret.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORRELATION_HOST` | `127.0.0.1` | Interface to bind |
| `CORRELATION_PORT` | `5001` | Port to bind |
| `CORRELATION_SERVICE_URL` | `http://<host>:<port>` | Address other services should use |
| `CORRELATION_TIMEOUT_SECONDS` | `30` | Runtime budget; slower requests are logged as slow |
| `CORRELATION_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `CORRELATION_LOG_FILE` | *(unset)* | If set, also write logs to this UTF-8 file |
| `CORRELATION_DEBUG` | `false` | Flask debug mode |

The active configuration is printed at startup and is also returned by
`/service-status` under `config`, so there is never any guessing about which
settings a running instance picked up.

---

## 3. Startup

From `correlation_alert/`, with the virtual environment active:

```
.venv\Scripts\Activate.ps1
python server.py
```

A healthy start looks like this:

```
[STARTUP] Correlation Alert Service starting
[STARTUP] service_url=http://127.0.0.1:5001
[STARTUP] request_timeout_seconds=30
[STARTUP] log_level=INFO
[STARTUP] log_file=None
[STARTUP] debug=False
 * Running on http://127.0.0.1:5001
```

To run on a different port, or to capture logs to a file:

```
$env:CORRELATION_PORT="5002"; python server.py
$env:CORRELATION_LOG_FILE="run.log"; python server.py
```

Clear an override with `$env:NAME=$null`.

---

## 4. Health check

```
GET http://127.0.0.1:5001/service-status
```

| Response | Meaning | Action |
| --- | --- | --- |
| `200` with `"ready": true` | Service is up and the pipeline executes | None |
| `503` with `"ready": false` | Service is up but cannot serve requests | See section 6.6 |
| No response at all | Process is not running | See section 6.1 |

The endpoint does not simply report that the process answered. It runs a small
synthetic dataset through the real pipeline before reporting healthy, so a green
result means the analysis path works rather than only that Flask is listening.

It also reports the installed `pandas` and `numpy` versions under `checks.dependencies`.
This matters because library versions differ in how they treat missing values and
zero-variance windows in rolling correlation, so two hosts on different versions
can produce different alert counts from the same file. Check these first when two
people disagree about a result.

---

## 5. Reading the logs

Every analysis request is assigned an eight-character request ID that appears on
every line for that request and is returned to the caller in the response body as
`request_id`. When someone reports a problem, ask for that ID.

A successful request:

```
[f22ed400] received source=file rows_in=1008 streams=['s1', 's2', 's3'] window_size=20 step_size=10 method=pearson
[f22ed400] completed rows_out=1008 windows=99 changes=294 alerts=19 imputed=0 coerced=0 runtime_ms=45
```

A rejected request:

```
[5c9063f9] invalid_input after 2ms: Requested stream(s) not found in the uploaded file: ['s99']. Available columns: ['time', 's1', 's2', 's3']
```

Log levels:

| Level | Used for |
| --- | --- |
| `INFO` | Normal progress, request received and completed |
| `WARNING` | Data was dropped or altered, or a request was rejected |
| `ERROR` | Unhandled failure, or the health check failed |

Set `CORRELATION_LOG_LEVEL=WARNING` during a demo to show only problems.

**What is deliberately not logged:** the contents of uploaded files. Row counts,
column names and parameters are recorded; the sensor readings themselves are not.

---

## 6. Common failures and recovery

### 6.1 Service does not start — `ModuleNotFoundError: No module named 'flask'`

The virtual environment is not active. Look for `(.venv)` at the start of the
prompt. If it is missing:

```
.venv\Scripts\Activate.ps1
```

### 6.2 Activation is blocked — `running scripts is disabled on this system`

Windows blocks unsigned scripts by default. Run once per user account, answer `Y`:

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 6.3 Port already in use — `Address already in use`

Another instance is still running. Either stop it, or start on another port:

```
$env:CORRELATION_PORT="5002"; python server.py
```

### 6.4 `400` with `"error_type": "invalid_input"`

The caller's request is wrong, not the service. The message names the problem
explicitly, including which columns the uploaded file actually contains. Common
causes:

- A stream name that is not in the file. Compare against the `Available columns`
  list in the message.
- A timestamp column that cannot be parsed at all, leaving no usable rows.

No service restart is needed. Fix the request and resend.

### 6.5 `400` with a missing parameter message

`timestamp_col` or `selected_streams` was not supplied. Both are required.

### 6.6 `503` from `/service-status`

The process is alive but the pipeline self-test failed. Read the `checks` object
in the response, which names the failing check and the error. Usual causes are a
broken or partial dependency install, or a code change that raises on import.

```
pip install -r ..\requirements.txt
```

Then restart and check again.

Note: `flask`, `flask-cors` and `requests` were missing from `requirements.txt`
until CCA121, so an environment built from that file before then will install the
analysis libraries but not the web framework, and the service will fail to start
with `ModuleNotFoundError: No module named 'flask'`. If you hit that on an older
environment, reinstall from the current file.

### 6.7 A request returns `200` but the numbers look wrong

Check `summary` in the response and the `completed` log line for that request ID:

- `rows_out` much lower than `rows_in` means rows were dropped during cleaning.
  The `WARNING` lines for that request say how many and why.
- `imputed` or `coerced` above zero means some values in the result were
  reconstructed rather than measured.
- `alerts: 0` with `windows: 0` means nothing was analysed at all.

Historically the service could return `200` with zero rows and report the run as
successful. That is no longer possible: an empty result after cleaning now raises
an error rather than reporting success.

### 6.8 A request is slow

Requests exceeding `CORRELATION_TIMEOUT_SECONDS` are logged as:

```
[<id>] slow request: runtime_ms=<n> exceeded budget of 30s
```

The request still completes. Runtime scales with row count and with the number of
windows, so a smaller `window_size` with a small `step_size` produces more windows
and takes longer.

---

## 7. Escalation

If the service is healthy but results are disputed, capture and share:

1. The `request_id` from the response
2. The `received` and `completed` log lines for that ID
3. The `checks.dependencies` block from `/service-status`

Those three together identify the input parameters, what the pipeline did with
them, and the library versions used, which is enough to reproduce the run.
