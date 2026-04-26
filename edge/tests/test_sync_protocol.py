from __future__ import annotations

import json

from edge.sync.sync_protocol import SyncEnvelope, SyncPayload, dedupe_key, serialize_envelopes, validate_sync_payload


def _build_payload() -> SyncPayload:
    return SyncPayload(
        event_id="evt_001",
        created_at="2026-01-01T00:00:00Z",
        media_type="image",
        media_sha256="abc123",
        predicted_label="REAL",
        predicted_probability=0.72,
        model_version="v1.0.0",
        model_source="onnx_local",
        threshold=0.5,
        privacy_mode="extension_minimum_retention",
        metadata={"allow_sync": True},
    )


def test_validate_sync_payload_success() -> None:
    payload = _build_payload()
    errors = validate_sync_payload(payload)
    assert errors == []


def test_validate_sync_payload_strict_local_rejects_allow_sync() -> None:
    payload = _build_payload()
    payload.privacy_mode = "strict_local"
    payload.metadata = {"allow_sync": True}

    errors = validate_sync_payload(payload)
    assert "strict_local privacy mode cannot explicitly allow sync" in errors


def test_dedupe_key_is_stable() -> None:
    payload = _build_payload()
    key1 = dedupe_key(payload)
    key2 = dedupe_key(payload)
    assert key1 == key2
    assert payload.media_sha256 in key1


def test_serialize_envelopes_roundtrip() -> None:
    envelope = SyncEnvelope(payload=_build_payload())
    raw = serialize_envelopes([envelope])
    loaded = json.loads(raw)

    restored = SyncEnvelope.from_dict(loaded[0])
    assert restored.payload.event_id == envelope.payload.event_id
    assert restored.status == envelope.status
