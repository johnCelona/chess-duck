"""Structured logging with secret redaction (ADR-0014)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_CONTEXT_FIELDS = ("job", "match", "game", "engine", "duck")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s,;\"']+"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\blip_[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)((?:access_?token|api_?token|code_verifier)\s*[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'&]+"),
)


def redact(text: str) -> str:
    """Remove anything token-shaped from a log line."""
    text = _SECRET_PATTERNS[0].sub(r"\1[redacted]", text)
    text = _SECRET_PATTERNS[1].sub(r"\1 [redacted]", text)
    text = _SECRET_PATTERNS[2].sub("[redacted]", text)
    return _SECRET_PATTERNS[3].sub(r"\1[redacted]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s  %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
