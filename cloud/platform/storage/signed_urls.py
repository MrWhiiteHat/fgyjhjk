"""Signed URL generation and verification for tenant storage objects."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

from cloud.platform.utils.exceptions import ValidationError
from cloud.platform.utils.security import constant_time_equal, hmac_sha256
from cloud.platform.utils.time import utc_now


class SignedUrlService:
    """Simple HMAC-based signed URL service."""

    def __init__(self, secret: str, base_url: str = "https://cloud.local/storage") -> None:
        self._secret = str(secret)
        self._base_url = str(base_url).rstrip("/")

    def generate(self, *, tenant_id: str, object_path: str, ttl_seconds: int) -> str:
        """Generate a signed download URL for a tenant object."""

        safe_tenant = str(tenant_id).strip()
        safe_object = str(object_path).strip().lstrip("/")
        if not safe_tenant or not safe_object:
            raise ValidationError("tenant_id and object_path are required")

        expiry = int(utc_now().timestamp()) + int(ttl_seconds)
        payload = f"{safe_tenant}:{safe_object}:{expiry}"
        signature = hmac_sha256(self._secret, payload)

        query = urlencode({"tenant": safe_tenant, "path": safe_object, "expires": expiry, "sig": signature})
        return f"{self._base_url}?{query}"

    def verify(self, signed_url: str) -> tuple[str, str]:
        """Verify signed URL and return tenant_id and object_path."""

        parsed = urlparse(str(signed_url))
        params = parse_qs(parsed.query)

        tenant = (params.get("tenant") or [""])[0]
        object_path = (params.get("path") or [""])[0]
        expires_raw = (params.get("expires") or [""])[0]
        signature = (params.get("sig") or [""])[0]

        if not tenant or not object_path or not expires_raw or not signature:
            raise ValidationError("Signed URL missing required query params")

        expires = int(expires_raw)
        now_ts = int(utc_now().timestamp())
        if now_ts > expires:
            raise ValidationError("Signed URL has expired")

        payload = f"{tenant}:{object_path}:{expires}"
        expected = hmac_sha256(self._secret, payload)
        if not constant_time_equal(signature, expected):
            raise ValidationError("Signed URL signature mismatch")

        return tenant, object_path
