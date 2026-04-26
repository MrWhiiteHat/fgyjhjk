"""In-memory status tracking for background explainability/report jobs."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.backend.config import get_settings
from app.backend.core.exceptions import PostprocessNotFoundError


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostprocessStatusService:
    """Track asynchronous postprocess work for image prediction requests."""

    _instance: "PostprocessStatusService | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()
        self._ttl_sec = int(self.settings.POSTPROCESS_STATUS_TTL_SEC)
        self._lock = threading.RLock()
        self._items: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "PostprocessStatusService":
        """Get singleton status service instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = PostprocessStatusService()
        return cls._instance

    def _cleanup_expired(self) -> None:
        cutoff = time.time() - float(self._ttl_sec)
        stale = [task_id for task_id, payload in self._items.items() if float(payload.get("created_at_epoch", 0.0)) < cutoff]
        for task_id in stale:
            self._items.pop(task_id, None)

    def create_task(self, prediction: Dict[str, Any], explain_requested: bool, report_requested: bool) -> Dict[str, Any]:
        """Create and store a new postprocess task record."""
        now_iso = _utc_now_iso()
        task_id = str(uuid.uuid4())

        explainability = None
        if explain_requested:
            explainability = {
                "status": "pending",
                "message": "Explainability queued",
                "requested": True,
            }

        report = None
        if report_requested:
            report = {
                "status": "pending",
                "message": "Report generation queued",
                "requested": True,
            }

        item = {
            "task_id": task_id,
            "status": "pending" if (explain_requested or report_requested) else "completed",
            "created_at": now_iso,
            "updated_at": now_iso,
            "created_at_epoch": time.time(),
            "prediction": dict(prediction),
            "explainability": explainability,
            "report": report,
            "error": None,
            "_flags": {
                "explain_requested": bool(explain_requested),
                "report_requested": bool(report_requested),
                "explain_done": not bool(explain_requested),
                "report_done": not bool(report_requested),
            },
        }

        with self._lock:
            self._cleanup_expired()
            self._items[task_id] = item

        return self._public_payload(item)

    def _public_payload(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": str(item.get("task_id", "")),
            "status": str(item.get("status", "pending")),
            "created_at": str(item.get("created_at", "")),
            "updated_at": str(item.get("updated_at", "")),
            "prediction": dict(item.get("prediction", {})),
            "explainability": item.get("explainability"),
            "report": item.get("report"),
            "error": item.get("error"),
        }

    def _get_item(self, task_id: str) -> Dict[str, Any]:
        item = self._items.get(task_id)
        if item is None:
            raise PostprocessNotFoundError(f"Postprocess task not found: {task_id}")
        return item

    def _update_state(self, item: Dict[str, Any]) -> None:
        flags = item.get("_flags", {})
        if item.get("error") is not None:
            item["status"] = "failed"
        elif bool(flags.get("explain_done", True)) and bool(flags.get("report_done", True)):
            item["status"] = "completed"
        elif bool(flags.get("explain_requested", False)) or bool(flags.get("report_requested", False)):
            item["status"] = "running"
        else:
            item["status"] = "completed"
        item["updated_at"] = _utc_now_iso()

    def set_explainability_result(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist explainability outputs for a task."""
        with self._lock:
            self._cleanup_expired()
            item = self._get_item(task_id)
            item["explainability"] = payload
            flags = item.get("_flags", {})
            flags["explain_done"] = True
            item["_flags"] = flags
            self._update_state(item)
            return self._public_payload(item)

    def set_report_result(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist report outputs for a task."""
        with self._lock:
            self._cleanup_expired()
            item = self._get_item(task_id)
            item["report"] = payload
            flags = item.get("_flags", {})
            flags["report_done"] = True
            item["_flags"] = flags
            self._update_state(item)
            return self._public_payload(item)

    def set_failed(self, task_id: str, stage: str, cause: str) -> Dict[str, Any]:
        """Persist failure state for a background task."""
        with self._lock:
            self._cleanup_expired()
            item = self._get_item(task_id)
            item["error"] = {
                "stage": str(stage),
                "cause": str(cause),
            }
            self._update_state(item)
            return self._public_payload(item)

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Return current task status payload."""
        with self._lock:
            self._cleanup_expired()
            item = self._get_item(task_id)
            return self._public_payload(item)
