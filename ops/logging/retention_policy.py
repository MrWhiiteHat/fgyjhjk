"""Retention policy manager for logs, temporary outputs, and reports."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class RetentionRule:
    """Retention rule for one managed directory."""

    name: str
    path: Path
    retention_days: int
    recursive: bool = True


class RetentionPolicyManager:
    """Applies safe retention cleanup under managed directories only."""

    def __init__(self, retention_days: int = 30) -> None:
        self.default_retention_days = int(retention_days)
        self.rules = [
            RetentionRule("app_logs", Path("app/backend/outputs/logs"), self.default_retention_days, True),
            RetentionRule("audit_logs", Path("app/backend/outputs/logs"), max(90, self.default_retention_days), True),
            RetentionRule("temp_files", Path("app/backend/tmp"), 2, True),
            RetentionRule("generated_reports", Path("app/backend/outputs/reports"), self.default_retention_days, True),
            RetentionRule("drift_reports", Path("app/backend/outputs/ops/drift/reports"), self.default_retention_days, True),
        ]

    @staticmethod
    def _now() -> float:
        return time.time()

    def _is_safe_path(self, root: Path, candidate: Path) -> bool:
        try:
            candidate.resolve().relative_to(root.resolve())
            return True
        except Exception:  # noqa: BLE001
            return False

    def _collect_files(self, rule: RetentionRule) -> List[Path]:
        if not rule.path.exists() or not rule.path.is_dir():
            return []
        if rule.recursive:
            return [item for item in rule.path.rglob("*") if item.is_file()]
        return [item for item in rule.path.iterdir() if item.is_file()]

    def cleanup(self, dry_run: bool = True) -> Dict[str, object]:
        """Apply retention cleanup rules with optional dry run mode."""
        now = self._now()
        summary: Dict[str, object] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "dry_run": bool(dry_run),
            "rules": [],
            "total_removed": 0,
            "total_candidates": 0,
        }

        for rule in self.rules:
            cutoff = now - (rule.retention_days * 24 * 60 * 60)
            files = self._collect_files(rule)
            candidates = [item for item in files if item.stat().st_mtime < cutoff]

            removed = []
            for file_path in candidates:
                if not self._is_safe_path(rule.path, file_path):
                    continue
                if not dry_run:
                    try:
                        file_path.unlink(missing_ok=True)
                    except OSError:
                        continue
                removed.append(str(file_path.as_posix()))

            summary["rules"].append(
                {
                    "name": rule.name,
                    "path": str(rule.path.as_posix()),
                    "retention_days": rule.retention_days,
                    "candidates": len(candidates),
                    "removed": len(removed),
                    "removed_files": removed,
                }
            )
            summary["total_candidates"] += len(candidates)
            summary["total_removed"] += len(removed)

        return summary
