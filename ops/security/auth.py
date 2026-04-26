"""Authentication and authorization helpers for API and admin operations."""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

try:
    from fastapi import HTTPException, Request, status
except Exception:  # noqa: BLE001
    HTTPException = RuntimeError  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]

    class status:  # type: ignore[override]
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403


@dataclass
class Principal:
    """Authenticated principal context."""

    key_id: str
    role: str


class AuthManager:
    """Simple API key authentication with role-based access control."""

    def __init__(self, config_path: str = "ops/configs/security_config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)
        self.api_key_enabled = bool(self.config.get("api_key_enabled", True))
        self.admin_roles = {str(role) for role in self.config.get("admin_roles", ["admin", "platform"])}
        self.public_roles = {str(role) for role in self.config.get("public_roles", ["public"])}
        self._key_map = self._load_keys()

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def _load_keys(self) -> Dict[str, Dict[str, str]]:
        """Load key map from environment.

        Expected env format for OPS_API_KEYS_JSON:
        {
          "public-client": {"key": "abc", "role": "public"},
          "admin-client": {"key": "def", "role": "admin"}
        }
        """
        payload = os.getenv("OPS_API_KEYS_JSON", "").strip()
        if payload:
            try:
                decoded = json.loads(payload)
                if isinstance(decoded, dict):
                    parsed: Dict[str, Dict[str, str]] = {}
                    for key_id, item in decoded.items():
                        if not isinstance(item, dict):
                            continue
                        key = str(item.get("key", ""))
                        role = str(item.get("role", "public"))
                        if key:
                            parsed[str(key_id)] = {"key": key, "role": role}
                    if parsed:
                        return parsed
            except json.JSONDecodeError:
                pass

        single_key = os.getenv("API_KEY", "").strip()
        if single_key:
            return {"default-client": {"key": single_key, "role": "admin"}}

        return {}

    def _match_key(self, provided_key: str) -> Optional[Principal]:
        for key_id, payload in self._key_map.items():
            candidate = str(payload.get("key", ""))
            role = str(payload.get("role", "public"))
            if candidate and hmac.compare_digest(provided_key, candidate):
                return Principal(key_id=key_id, role=role)
        return None

    def authenticate(self, provided_key: str | None) -> Principal:
        if not self.api_key_enabled:
            return Principal(key_id="anonymous", role="public")

        if not provided_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "AUTH_REQUIRED", "message": "API key is required"},
            )

        principal = self._match_key(str(provided_key))
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "AUTH_INVALID", "message": "Invalid API key"},
            )

        return principal

    def authorize(self, principal: Principal, required_scope: str) -> None:
        scope = str(required_scope).lower()
        if scope == "public":
            return
        if scope == "admin" and principal.role in self.admin_roles:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "AUTH_FORBIDDEN",
                "message": "Insufficient role for requested operation",
                "required_scope": scope,
                "principal_role": principal.role,
            },
        )

    def authenticate_and_authorize(self, provided_key: str | None, required_scope: str) -> Principal:
        principal = self.authenticate(provided_key)
        self.authorize(principal, required_scope=required_scope)
        return principal


def extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from standard headers."""
    header_value = request.headers.get("X-API-Key") if hasattr(request, "headers") else None
    if header_value:
        return header_value
    auth_header = request.headers.get("Authorization", "") if hasattr(request, "headers") else ""
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def enforce_public_access(request: Request, auth_manager: AuthManager) -> Principal:
    """Auth helper for public inference endpoints."""
    key = extract_api_key(request)
    return auth_manager.authenticate_and_authorize(key, required_scope="public")


def enforce_admin_access(request: Request, auth_manager: AuthManager) -> Principal:
    """Deny-by-default helper for admin endpoints when auth is enabled."""
    key = extract_api_key(request)
    return auth_manager.authenticate_and_authorize(key, required_scope="admin")
