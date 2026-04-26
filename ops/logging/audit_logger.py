"""Immutable-style audit logger for privileged operations."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class AuditEvent:
    """Audit event payload for sensitive actions."""

    actor: str
    action: str
    target: str
    outcome: str
    request_id: str
    timestamp: str
    details: Dict[str, object] = field(default_factory=dict)
    prev_hash: str = ""
    event_hash: str = ""


class AuditLogger:
    """Append-only audit logger with hash-chain integrity hints."""

    def __init__(self, log_file: str = "app/backend/outputs/logs/audit.log") -> None:
        self.log_path = Path(log_file)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _last_event_hash(self) -> str:
        if not self.log_path.exists():
            return ""
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle.readlines() if line.strip()]
            if not lines:
                return ""
            payload = json.loads(lines[-1])
            return str(payload.get("event_hash", ""))
        except (OSError, json.JSONDecodeError):
            return ""

    @staticmethod
    def _compute_hash(payload: Dict[str, object]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def log_event(
        self,
        actor: str,
        action: str,
        target: str,
        outcome: str,
        request_id: str,
        details: Dict[str, object] | None = None,
    ) -> AuditEvent:
        """Record one auditable event with chain hash."""
        event = AuditEvent(
            actor=str(actor),
            action=str(action),
            target=str(target),
            outcome=str(outcome),
            request_id=str(request_id),
            timestamp=self._now_iso(),
            details=details or {},
            prev_hash=self._last_event_hash(),
        )

        body = asdict(event)
        body["event_hash"] = ""
        event.event_hash = self._compute_hash(body)

        payload = asdict(event)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return event

    def verify_chain(self) -> Dict[str, object]:
        """Verify hash chain continuity and detect tampering hints."""
        if not self.log_path.exists():
            return {"valid": True, "events": 0, "errors": []}

        errors: List[str] = []
        previous_hash = ""
        event_count = 0

        with self.log_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                event_count += 1
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    errors.append(f"line {line_number}: invalid JSON: {exc}")
                    continue

                stored_hash = str(payload.get("event_hash", ""))
                prev_hash = str(payload.get("prev_hash", ""))
                if prev_hash != previous_hash:
                    errors.append(f"line {line_number}: prev_hash mismatch")

                payload_for_hash = dict(payload)
                payload_for_hash["event_hash"] = ""
                computed_hash = self._compute_hash(payload_for_hash)
                if computed_hash != stored_hash:
                    errors.append(f"line {line_number}: event_hash mismatch")

                previous_hash = stored_hash

        return {
            "valid": len(errors) == 0,
            "events": event_count,
            "errors": errors,
        }
