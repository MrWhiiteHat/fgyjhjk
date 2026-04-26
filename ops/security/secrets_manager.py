"""Secrets manager for environment and file-based secret loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


class SecretsManager:
    """Loads secrets from environment variables and optional mounted files."""

    def __init__(self, secrets_dir: str | None = None) -> None:
        self.secrets_dir = Path(secrets_dir) if secrets_dir else None

    def _read_secret_file(self, name: str) -> Optional[str]:
        if self.secrets_dir is None:
            return None
        path = self.secrets_dir / name
        if not path.exists() or not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    def get_optional(self, key: str, file_name: str | None = None, default: str | None = None) -> Optional[str]:
        env_value = os.getenv(key)
        if env_value is not None and env_value.strip() != "":
            return env_value.strip()

        if file_name:
            file_value = self._read_secret_file(file_name)
            if file_value:
                return file_value

        return default

    def get_required(self, key: str, file_name: str | None = None) -> str:
        value = self.get_optional(key=key, file_name=file_name)
        if value is None or value == "":
            raise RuntimeError(f"Missing required secret: {key}")
        return value

    @staticmethod
    def redact_value(value: str, visible_chars: int = 2) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) <= visible_chars * 2:
            return "*" * len(text)
        return f"{text[:visible_chars]}{'*' * (len(text) - (visible_chars * 2))}{text[-visible_chars:]}"

    @staticmethod
    def redact_mapping(payload: Dict[str, object], sensitive_keys: list[str] | None = None) -> Dict[str, object]:
        sensitive = {key.lower() for key in (sensitive_keys or ["api_key", "token", "secret", "password", "authorization"])}
        redacted: Dict[str, object] = {}
        for key, value in payload.items():
            if key.lower() in sensitive and value is not None:
                redacted[key] = SecretsManager.redact_value(str(value))
            else:
                redacted[key] = value
        return redacted
