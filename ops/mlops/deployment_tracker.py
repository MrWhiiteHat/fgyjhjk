"""Deployment tracking for promotions and rollbacks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List


class DeploymentTracker:
    """Appends deployment events to a JSONL history store."""

    def __init__(self, history_path: str = "ops/mlops/state/deployment_history.jsonl") -> None:
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def record(
        self,
        action: str,
        model_version: str,
        stage: str,
        actor: str,
        reason: str,
        outcome: str,
        metadata: Dict[str, object] | None = None,
    ) -> Dict[str, object]:
        event = {
            "timestamp": self._now_iso(),
            "action": str(action),
            "model_version": str(model_version),
            "stage": str(stage),
            "actor": str(actor),
            "reason": str(reason),
            "outcome": str(outcome),
            "metadata": metadata or {},
        }
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def list_history(self, limit: int = 200) -> List[Dict[str, object]]:
        if not self.history_path.exists():
            return []
        rows: List[Dict[str, object]] = []
        with self.history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-int(limit) :]

    def production_events(self, limit: int = 50) -> List[Dict[str, object]]:
        events = [event for event in self.list_history(limit=2000) if event.get("stage") == "production"]
        return events[-int(limit) :]
