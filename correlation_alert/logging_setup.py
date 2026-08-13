"""Logging setup for the Correlation Change Alert service.

The service previously wrote progress with bare print() calls, which meant no
severity levels, no timestamps, and no way to turn the volume down. This module
configures a single named logger tree ("correlation") so that every module logs
through the same handler at the level set by CORRELATION_LOG_LEVEL.

Use get_logger(__name__-ish string) rather than logging.getLogger directly, so
that configuration is applied before the first record is emitted.

CCA121.
"""
import logging
import os
import sys

import config

ROOT_NAME = "correlation"

_configured = False


def configure_logging() -> None:
    """Attach a single stdout handler to the 'correlation' logger tree.

    Safe to call more than once; only the first call does any work.
    """
    global _configured
    if _configured:
        return

    level = getattr(logging, config.LOG_LEVEL, None)
    if not isinstance(level, int):
        level = logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)-24s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger(ROOT_NAME)
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Optional file handler. Written as UTF-8 so the file is readable on any
    # platform, rather than whatever the shell would have encoded a redirect as.
    if config.LOG_FILE:
        directory = os.path.dirname(os.path.abspath(config.LOG_FILE))
        if directory:
            os.makedirs(directory, exist_ok=True)
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Do not also emit through Flask's root handler, which would double each line.
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger namespaced under the service root."""
    configure_logging()
    return logging.getLogger(f"{ROOT_NAME}.{name}")
