from __future__ import annotations

from pathlib import Path

from edge.sync.offline_queue import OfflineQueue
from edge.sync.sync_protocol import SyncPayload


def _build_payload(event_id: str = "evt_001") -> SyncPayload:
    return SyncPayload(
        event_id=event_id,
        created_at="2026-01-01T00:00:00Z",
        media_type="image",
        media_sha256="abc123",
        predicted_label="REAL",
        predicted_probability=0.9,
        model_version="v1.0.0",
        model_source="onnx_local",
        threshold=0.5,
        privacy_mode="extension_minimum_retention",
    )


def test_offline_queue_deduplicates_pending_items(tmp_path: Path) -> None:
    queue_path = tmp_path / "offline_queue.json"
    queue = OfflineQueue(queue_path=str(queue_path))

    first = queue.enqueue(_build_payload("evt_001"))
    second = queue.enqueue(_build_payload("evt_001"))

    items = queue.list()
    assert first.payload.event_id == second.payload.event_id
    assert len(items) == 1


def test_offline_queue_status_flow_and_cleanup(tmp_path: Path) -> None:
    queue_path = tmp_path / "offline_queue.json"
    queue = OfflineQueue(queue_path=str(queue_path))

    queue.enqueue(_build_payload("evt_101"))
    queue.mark_syncing("evt_101")

    syncing_item = queue.list()[0]
    assert syncing_item.status == "syncing"
    assert syncing_item.attempts == 1

    queue.mark_failed("evt_101", "temporary failure")
    failed_item = queue.list()[0]
    assert failed_item.status == "failed"
    assert failed_item.attempts == 2
    assert failed_item.last_error == "temporary failure"

    queue.mark_synced("evt_101")
    removed = queue.remove_synced()

    assert removed == 1
    assert queue.list() == []
