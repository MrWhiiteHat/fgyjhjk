"""Shared sync protocol contracts for edge and backend reconciliation."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SyncStatus = Literal["pending", "syncing", "synced", "failed", "conflict"]
MediaType = Literal["image", "video", "camera_frame"]


@dataclass
class SyncPayload:
    """A queued edge inference payload to synchronize with backend."""

    event_id: str
    created_at: str
    media_type: MediaType
    media_sha256: str
    predicted_label: str
    predicted_probability: float
    model_version: str
    model_source: str
    threshold: float
    privacy_mode: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncEnvelope:
    """Queue envelope that tracks lifecycle state for one payload."""

    payload: SyncPayload
    status: SyncStatus = "pending"
    attempts: int = 0
    last_error: str = ""
    last_attempt_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncEnvelope":
        payload_data = dict(data.get("payload", {}))
        payload = SyncPayload(
            event_id=str(payload_data.get("event_id", "")),
            created_at=str(payload_data.get("created_at", "")),
            media_type=str(payload_data.get("media_type", "image")),
            media_sha256=str(payload_data.get("media_sha256", "")),
            predicted_label=str(payload_data.get("predicted_label", "")),
            predicted_probability=float(payload_data.get("predicted_probability", 0.0)),
            model_version=str(payload_data.get("model_version", "")),
            model_source=str(payload_data.get("model_source", "")),
            threshold=float(payload_data.get("threshold", 0.5)),
            privacy_mode=str(payload_data.get("privacy_mode", "strict_local")),
            metadata=dict(payload_data.get("metadata", {})),
        )
        return cls(
            payload=payload,
            status=str(data.get("status", "pending")),
            attempts=int(data.get("attempts", 0)),
            last_error=str(data.get("last_error", "")),
            last_attempt_at=str(data.get("last_attempt_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def validate_sync_payload(payload: SyncPayload) -> list[str]:
    """Validate protocol-level required fields before upload attempt."""
    errors: list[str] = []

    if not payload.event_id:
        errors.append("event_id is required")
    if not payload.created_at:
        errors.append("created_at is required")
    if payload.media_type not in {"image", "video", "camera_frame"}:
        errors.append("media_type is invalid")
    if not payload.media_sha256:
        errors.append("media_sha256 is required")
    if payload.predicted_label not in {"REAL", "FAKE", "UNKNOWN"}:
        errors.append("predicted_label must be REAL, FAKE, or UNKNOWN")
    if not (0.0 <= payload.predicted_probability <= 1.0):
        errors.append("predicted_probability must be in [0, 1]")
    if not payload.model_version:
        errors.append("model_version is required")
    if payload.privacy_mode == "strict_local" and payload.metadata.get("allow_sync") is True:
        errors.append("strict_local privacy mode cannot explicitly allow sync")

    return errors


def dedupe_key(payload: SyncPayload) -> str:
    """Deterministic dedupe key for queue coalescing."""
    return f"{payload.media_sha256}:{payload.model_version}:{payload.threshold:.4f}:{payload.media_type}"


def serialize_envelopes(items: list[SyncEnvelope]) -> str:
    """Serialize envelope collection to JSON string."""
    return json.dumps([item.to_dict() for item in items], sort_keys=True)
