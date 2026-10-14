"""JSON logs on stderr, one event per line, so journald can store them."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Encode a log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Attach the JSON formatter to the root logger once."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("atlas")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``atlas`` namespace."""
    configure_logging()
    return logging.getLogger(name if name.startswith("atlas") else f"atlas.{name}")


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    """Write one structured event. String fields are redacted before they hit stderr."""
    safe = {key: _redact(value) for key, value in fields.items()}
    logger.log(level, event, extra={"fields": safe})


def _redact(value: object) -> object:
    if not isinstance(value, str):
        return value
    from atlas.redact import mask_secrets

    return mask_secrets(value)
