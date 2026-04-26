"""Identifier generation helpers."""

from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a stable prefixed identifier."""

    if not prefix or not str(prefix).strip():
        raise ValueError("prefix is required")
    return f"{prefix}_{uuid4().hex}"
