"""Custom exceptions used throughout cloud platform services."""

from __future__ import annotations


class CloudPlatformError(Exception):
    """Base class for cloud platform errors."""


class ValidationError(CloudPlatformError):
    """Raised when input validation fails."""


class NotFoundError(CloudPlatformError):
    """Raised when a requested resource does not exist."""


class AuthorizationError(CloudPlatformError):
    """Raised when access is denied due to role or permission checks."""


class TenantIsolationError(CloudPlatformError):
    """Raised when an operation attempts cross-tenant access."""


class QuotaExceededError(CloudPlatformError):
    """Raised when a tenant exceeds a hard usage limit."""


class IdempotencyConflictError(CloudPlatformError):
    """Raised when idempotency key is reused with mismatched payload."""
