"""Per-inference and batch cost estimation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import yaml


@dataclass
class InferenceCostInput:
    """Input dimensions for per-request cost estimation."""

    latency_ms: float
    output_bytes: int
    used_gpu: bool


class InferenceCostEstimator:
    """Estimates request and aggregate costs from configured rate card."""

    def __init__(self, budget_config_path: str = "ops/cost/budget_alerts.yaml") -> None:
        self.budget_config_path = Path(budget_config_path)
        self.config = self._load_config(self.budget_config_path)
        rates = dict(self.config.get("cost_rates", {}))
        self.cpu_second_usd = float(rates.get("cpu_second_usd", 0.00005))
        self.gpu_second_usd = float(rates.get("gpu_second_usd", 0.00120))
        self.egress_gb_usd = float(rates.get("egress_gb_usd", 0.090))

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def estimate_request(self, request: InferenceCostInput) -> Dict[str, float]:
        seconds = max(0.0, float(request.latency_ms) / 1000.0)
        compute = seconds * (self.gpu_second_usd if request.used_gpu else self.cpu_second_usd)
        egress = (max(0, int(request.output_bytes)) / (1024.0**3)) * self.egress_gb_usd
        total = compute + egress
        return {
            "compute_usd": round(compute, 8),
            "egress_usd": round(egress, 8),
            "total_usd": round(total, 8),
        }

    def estimate_batch(self, requests: Iterable[InferenceCostInput]) -> Dict[str, float]:
        compute = 0.0
        egress = 0.0
        count = 0
        for item in requests:
            partial = self.estimate_request(item)
            compute += partial["compute_usd"]
            egress += partial["egress_usd"]
            count += 1
        total = compute + egress
        return {
            "requests": count,
            "compute_usd": round(compute, 8),
            "egress_usd": round(egress, 8),
            "total_usd": round(total, 8),
        }
