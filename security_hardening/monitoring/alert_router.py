"""Alert routing for security events to logging and ops hooks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from security_hardening.monitoring.security_events import SecurityEvent


@dataclass
class AlertRouterConfig:
    """Config for route destinations and severity thresholds."""

    min_severity_for_ops: str = "high"
    log_path: str = "security_hardening/security_alerts.log"


class AlertRouter:
    """Routes alerts to structured logs and optional callback hooks."""

    _severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self, config: AlertRouterConfig | None = None, ops_hook: Callable[[SecurityEvent], None] | None = None) -> None:
        self.config = config or AlertRouterConfig()
        self.ops_hook = ops_hook

    def route(self, event: SecurityEvent) -> dict[str, bool]:
        """Route event to log and optional ops hook based on severity."""

        logged = self._log_event(event)
        routed_to_ops = False

        min_rank = self._severity_rank.get(self.config.min_severity_for_ops, 3)
        event_rank = self._severity_rank.get(event.severity, 1)
        if event_rank >= min_rank and self.ops_hook is not None:
            self.ops_hook(event)
            routed_to_ops = True

        return {
            "logged": logged,
            "routed_to_ops": routed_to_ops,
        }

    def _log_event(self, event: SecurityEvent) -> bool:
        """Append event to JSONL log file."""

        path = Path(self.config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")
        return True
