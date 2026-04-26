"""Structured logging utilities with redaction and JSON formatting."""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List

import yaml


_DEFAULT_REDACTION_KEYS = [
    "api_key",
    "authorization",
    "token",
    "secret",
    "password",
]


class SensitiveDataFilter(logging.Filter):
    """Redacts sensitive values from log messages and extra payloads."""

    def __init__(self, keys_to_redact: Iterable[str] | None = None) -> None:
        super().__init__()
        keys = keys_to_redact or _DEFAULT_REDACTION_KEYS
        self.patterns = [re.compile(rf"({re.escape(key)}\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE) for key in keys]

    def filter(self, record: logging.LogRecord) -> bool:
        message = str(record.getMessage())
        for pattern in self.patterns:
            message = pattern.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """JSON log formatter with required structured fields."""

    def __init__(self, service_name: str, environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    @staticmethod
    def _now_iso(created: float) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created))

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self._now_iso(record.created),
            "level": record.levelname,
            "service_name": self.service_name,
            "environment": self.environment,
            "request_id": getattr(record, "request_id", ""),
            "endpoint": getattr(record, "endpoint", ""),
            "model_version": getattr(record, "model_version", ""),
            "event_type": getattr(record, "event_type", "application"),
            "message": record.getMessage(),
            "logger": record.name,
        }
        return json.dumps(payload, sort_keys=True)


def _load_log_config(path: str = "ops/logging/log_config.yaml") -> Dict[str, object]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload if isinstance(payload, dict) else {}


def configure_structured_logger(
    logger_name: str,
    service_name: str,
    environment: str,
    log_dir: str = "app/backend/outputs/logs",
    config_path: str = "ops/logging/log_config.yaml",
) -> logging.Logger:
    """Configure and return a structured logger with console and file handlers."""
    config = _load_log_config(config_path)

    level_name = str(config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_directory = Path(config.get("log_dir", log_dir))
    log_directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    redaction_enabled = bool(config.get("redaction_enabled", True))
    redaction_keys = list(config.get("redaction_keys", _DEFAULT_REDACTION_KEYS))

    formatter_type = str(config.get("format", "json")).lower()
    formatter = JsonFormatter(service_name=service_name, environment=environment)
    if formatter_type != "json":
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s [%(event_type)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    if bool(config.get("console_enabled", True)):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        if redaction_enabled:
            console_handler.addFilter(SensitiveDataFilter(keys_to_redact=redaction_keys))
        logger.addHandler(console_handler)

    if bool(config.get("file_enabled", True)):
        filename = str(config.get("file_name", f"{logger_name.replace('.', '_')}.log"))
        file_path = log_directory / filename
        max_bytes = int(config.get("max_bytes", 10 * 1024 * 1024))
        backup_count = int(config.get("backup_count", 10))

        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        if redaction_enabled:
            file_handler.addFilter(SensitiveDataFilter(keys_to_redact=redaction_keys))
        logger.addHandler(file_handler)

    return logger


class ContextLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter to include request/endpoint/model context in logs."""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        merged = dict(self.extra)
        merged.update(extra)
        kwargs["extra"] = merged
        return msg, kwargs


def get_context_logger(base_logger: logging.Logger, context: Dict[str, str] | None = None) -> ContextLoggerAdapter:
    """Return context-bound logger adapter for request-level fields."""
    return ContextLoggerAdapter(base_logger, context or {})
