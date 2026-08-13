"""Runtime configuration for the Correlation Change Alert service.

Every setting is read from an environment variable with a safe default, so the
same code runs unchanged on a laptop and on a deployed host. Nothing in here is
a secret, and secrets must never be given defaults in source.

CCA121.
"""
import os


def _int_from_env(name: str, default: int) -> int:
    """Read an integer setting, falling back to the default if it is unusable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Where the service binds.
HOST = os.getenv("CORRELATION_HOST", "127.0.0.1")
PORT = _int_from_env("CORRELATION_PORT", 5001)

# The address other services and the runbook should use to reach this service.
SERVICE_URL = os.getenv("CORRELATION_SERVICE_URL", f"http://{HOST}:{PORT}")

# Seconds a single analysis request is expected to complete within. Requests
# exceeding this are logged as slow so they can be found again after a demo.
REQUEST_TIMEOUT_SECONDS = _int_from_env("CORRELATION_TIMEOUT_SECONDS", 30)

# DEBUG, INFO, WARNING or ERROR.
LOG_LEVEL = os.getenv("CORRELATION_LOG_LEVEL", "INFO").upper()

# Optional path to also write logs to a UTF-8 file. Empty means console only.
LOG_FILE = os.getenv("CORRELATION_LOG_FILE", "").strip()

# Flask debug mode. Off unless explicitly enabled.
DEBUG = os.getenv("CORRELATION_DEBUG", "false").strip().lower() == "true"


def as_dict() -> dict:
    """Non-secret configuration, safe to expose on the health endpoint."""
    return {
        "service_url": SERVICE_URL,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "log_level": LOG_LEVEL,
        "log_file": LOG_FILE or None,
        "debug": DEBUG,
    }
