"""Storage usage tracker for dataset, artifacts, logs, and reports."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import yaml


class StorageTracker:
    """Computes storage footprint and monthly storage cost estimate."""

    def __init__(self, budget_config_path: str = "ops/cost/budget_alerts.yaml") -> None:
        self.budget_config_path = Path(budget_config_path)
        self.config = self._load_config(self.budget_config_path)

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _dir_size_bytes(path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        for root, _, files in os.walk(path):
            for name in files:
                candidate = Path(root) / name
                try:
                    total += candidate.stat().st_size
                except OSError:
                    continue
        return total

    def summarize(self) -> Dict[str, object]:
        tracked = {
            "dataset": Path("dataset"),
            "training_outputs": Path("training/outputs"),
            "ops_state": Path("ops/mlops/state"),
            "ops_logs": Path("ops/logs"),
            "ops_reports": Path("ops/reports"),
            "backups": Path("ops/backups/archives"),
        }

        breakdown = {name: self._dir_size_bytes(path) for name, path in tracked.items()}
        total_bytes = sum(breakdown.values())
        total_gb = total_bytes / (1024.0**3)

        storage_rate = float(dict(self.config.get("cost_rates", {})).get("storage_gb_month_usd", 0.023))
        estimated_storage_usd = total_gb * storage_rate

        budget = float(dict(self.config.get("budgets", {})).get("storage_usd", 0.0))
        percent_of_budget = ((estimated_storage_usd / budget) * 100.0) if budget > 0 else None

        return {
            "total_bytes": int(total_bytes),
            "total_gb": round(total_gb, 6),
            "breakdown_bytes": breakdown,
            "estimated_storage_usd": round(estimated_storage_usd, 6),
            "storage_budget_usd": budget,
            "percent_of_storage_budget": round(percent_of_budget, 2) if percent_of_budget is not None else None,
        }
