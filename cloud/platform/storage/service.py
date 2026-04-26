"""Tenant-isolated object storage helper."""

from __future__ import annotations

from pathlib import Path

from cloud.platform.storage.retention import RetentionPolicyService
from cloud.platform.storage.signed_urls import SignedUrlService
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import ValidationError


class TenantStorageService:
    """Stores and retrieves tenant objects under isolated directory trees."""

    def __init__(self, *, storage_root: Path, signed_url_service: SignedUrlService) -> None:
        self._storage_root = Path(storage_root)
        self._signed_urls = signed_url_service
        self._retention = RetentionPolicyService()
        self._storage_root.mkdir(parents=True, exist_ok=True)

    def tenant_root(self, tenant_id: str) -> Path:
        """Return tenant root path and ensure directory exists."""

        safe_tenant = str(tenant_id).strip()
        if not safe_tenant:
            raise ValidationError("tenant_id is required")

        root = self._storage_root / safe_tenant
        root.mkdir(parents=True, exist_ok=True)
        return root

    def put_bytes(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        object_path: str,
        content: bytes,
    ) -> Path:
        """Persist bytes under tenant-isolated path."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        target = self._resolve_tenant_path(tenant_id=tenant_id, object_path=object_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def read_bytes(self, *, actor_tenant_id: str, tenant_id: str, object_path: str) -> bytes:
        """Read bytes from tenant path with strict tenant guard."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        target = self._resolve_tenant_path(tenant_id=tenant_id, object_path=object_path)
        return target.read_bytes()

    def create_signed_url(self, *, actor_tenant_id: str, tenant_id: str, object_path: str, ttl_seconds: int) -> str:
        """Create signed URL for tenant object access."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        safe_object = self._normalize_object_path(object_path)
        return self._signed_urls.generate(tenant_id=tenant_id, object_path=safe_object, ttl_seconds=ttl_seconds)

    def verify_signed_url(self, signed_url: str) -> tuple[str, str]:
        """Verify signed URL and return tenant/object pair."""

        return self._signed_urls.verify(signed_url)

    def apply_retention(self, *, actor_tenant_id: str, tenant_id: str, max_age_seconds: int) -> int:
        """Apply retention policy to a tenant storage tree."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        root = self.tenant_root(tenant_id)
        return self._retention.sweep(tenant_root=root, max_age_seconds=max_age_seconds)

    def _resolve_tenant_path(self, *, tenant_id: str, object_path: str) -> Path:
        safe_object = self._normalize_object_path(object_path)
        root = self.tenant_root(tenant_id)
        target = root / safe_object
        resolved_target = target.resolve()
        resolved_root = root.resolve()
        if resolved_root not in resolved_target.parents and resolved_target != resolved_root:
            raise ValidationError("Object path escapes tenant root")
        return resolved_target

    @staticmethod
    def _normalize_object_path(object_path: str) -> str:
        safe_path = str(object_path).replace("\\", "/").strip().lstrip("/")
        if not safe_path or ".." in safe_path.split("/"):
            raise ValidationError("Invalid object_path")
        return safe_path
