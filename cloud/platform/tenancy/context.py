"""Tenant context propagation helpers using context variables."""

from __future__ import annotations

from contextvars import ContextVar, Token

from cloud.platform.utils.exceptions import ValidationError

_tenant_context: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def set_tenant_context(tenant_id: str) -> Token:
    """Set tenant context for current execution flow."""

    if not tenant_id or not str(tenant_id).strip():
        raise ValidationError("tenant_id is required")
    return _tenant_context.set(str(tenant_id).strip())


def get_tenant_context(required: bool = True) -> str | None:
    """Read tenant context from current execution flow."""

    value = _tenant_context.get()
    if required and not value:
        raise ValidationError("Tenant context is missing")
    return value


def clear_tenant_context(token: Token | None = None) -> None:
    """Clear tenant context safely."""

    if token is not None:
        _tenant_context.reset(token)
        return
    _tenant_context.set(None)
