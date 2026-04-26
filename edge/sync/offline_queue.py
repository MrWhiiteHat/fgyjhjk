"""Persistent offline queue for mobile and extension sync events."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from edge.sync.sync_protocol import SyncEnvelope, SyncPayload, dedupe_key, now_iso


class OfflineQueue:
    """File-backed queue with deduplication and status updates."""

    def __init__(self, queue_path: str = "edge/sync/state/offline_queue.json") -> None:
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self.queue_path.exists():
            self.queue_path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[SyncEnvelope]:
        with self.queue_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, list):
            return []
        return [SyncEnvelope.from_dict(item) for item in raw if isinstance(item, dict)]

    def _write(self, items: list[SyncEnvelope]) -> None:
        with self.queue_path.open("w", encoding="utf-8") as handle:
            json.dump([item.to_dict() for item in items], handle, indent=2, sort_keys=True)

    def list(self) -> list[SyncEnvelope]:
        with self._lock:
            return self._read()

    def enqueue(self, payload: SyncPayload) -> SyncEnvelope:
        with self._lock:
            current = self._read()
            key = dedupe_key(payload)
            for item in current:
                if dedupe_key(item.payload) == key and item.status in {"pending", "syncing"}:
                    return item

            envelope = SyncEnvelope(
                payload=payload,
                status="pending",
                attempts=0,
                last_error="",
                last_attempt_at="",
                updated_at=now_iso(),
            )
            current.append(envelope)
            self._write(current)
            return envelope

    def mark_syncing(self, event_id: str) -> None:
        self._update_status(event_id=event_id, status="syncing")

    def mark_synced(self, event_id: str) -> None:
        self._update_status(event_id=event_id, status="synced", clear_error=True)

    def mark_failed(self, event_id: str, error: str) -> None:
        self._update_status(event_id=event_id, status="failed", error=error)

    def mark_conflict(self, event_id: str, error: str) -> None:
        self._update_status(event_id=event_id, status="conflict", error=error)

    def _update_status(self, event_id: str, status: str, error: str = "", clear_error: bool = False) -> None:
        with self._lock:
            current = self._read()
            for item in current:
                if item.payload.event_id == event_id:
                    item.status = status
                    item.attempts += 1 if status in {"syncing", "failed", "conflict"} else item.attempts
                    item.last_attempt_at = now_iso()
                    item.updated_at = now_iso()
                    if clear_error:
                        item.last_error = ""
                    elif error:
                        item.last_error = str(error)
                    break
            self._write(current)

    def pending_items(self) -> list[SyncEnvelope]:
        with self._lock:
            return [item for item in self._read() if item.status in {"pending", "failed"}]

    def remove_synced(self) -> int:
        with self._lock:
            current = self._read()
            kept = [item for item in current if item.status != "synced"]
            removed = len(current) - len(kept)
            self._write(kept)
            return removed

    def clear(self) -> None:
        with self._lock:
            self._write([])
