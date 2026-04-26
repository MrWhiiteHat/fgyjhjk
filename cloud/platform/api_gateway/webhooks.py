"""Webhook signing and verification utilities."""

from __future__ import annotations

from cloud.platform.utils.exceptions import ValidationError
from cloud.platform.utils.security import constant_time_equal, hmac_sha256
from cloud.platform.utils.time import utc_now


class WebhookSigningService:
    """Signs and verifies webhook payloads using shared secret HMAC."""

    def __init__(self, secret: str) -> None:
        self._secret = str(secret)

    def sign(self, payload: str, timestamp_epoch: int | None = None) -> str:
        """Generate signature header payload for outgoing webhooks."""

        ts = int(timestamp_epoch) if timestamp_epoch is not None else int(utc_now().timestamp())
        data = f"{ts}.{payload}"
        signature = hmac_sha256(self._secret, data)
        return f"t={ts},v1={signature}"

    def verify(self, *, payload: str, signature_header: str, tolerance_seconds: int = 300) -> bool:
        """Verify incoming webhook signature and timestamp tolerance."""

        parts = {}
        for chunk in str(signature_header).split(","):
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            parts[key.strip()] = value.strip()

        if "t" not in parts or "v1" not in parts:
            raise ValidationError("Invalid signature header format")

        timestamp = int(parts["t"])
        signature = parts["v1"]
        now_ts = int(utc_now().timestamp())

        if abs(now_ts - timestamp) > int(tolerance_seconds):
            raise ValidationError("Webhook signature timestamp outside tolerance")

        expected = hmac_sha256(self._secret, f"{timestamp}.{payload}")
        if not constant_time_equal(signature, expected):
            raise ValidationError("Webhook signature mismatch")

        return True
