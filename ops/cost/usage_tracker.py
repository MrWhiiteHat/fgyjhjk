"""Inference usage tracker with rolling summaries and budget comparison."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import yaml


class UsageTracker:
    """Tracks inference events and estimates compute/egress costs."""

    def __init__(
        self,
        events_path: str = "ops/cost/state/usage_events.jsonl",
        budget_config_path: str = "ops/cost/budget_alerts.yaml",
    ) -> None:
        self.events_path = Path(events_path)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.budget_config_path = Path(budget_config_path)
        self.config = self._load_config(self.budget_config_path)

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def record_event(
        self,
        endpoint: str,
        latency_ms: float,
        input_bytes: int,
        output_bytes: int,
        used_gpu: bool,
    ) -> Dict[str, object]:
        event = {
            "timestamp": self._now_iso(),
            "endpoint": str(endpoint),
            "latency_ms": float(latency_ms),
            "input_bytes": int(input_bytes),
            "output_bytes": int(output_bytes),
            "used_gpu": bool(used_gpu),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def _read_events(self, limit: int = 200000) -> List[Dict[str, object]]:
        if not self.events_path.exists():
            return []
        rows: List[Dict[str, object]] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-int(limit) :]

    def summarize(self) -> Dict[str, object]:
        events = self._read_events()
        rates = dict(self.config.get("cost_rates", {}))
        budgets = dict(self.config.get("budgets", {}))
        warning_pct = float(dict(self.config.get("thresholds", {})).get("warning_percent", 80))
        critical_pct = float(dict(self.config.get("thresholds", {})).get("critical_percent", 95))

        by_endpoint = defaultdict(int)
        total_latency_ms = 0.0
        total_input = 0
        total_output = 0
        gpu_count = 0

        inference_compute_usd = 0.0
        gpu_runtime_usd = 0.0
        egress_usd = 0.0

        cpu_rate = float(rates.get("cpu_second_usd", 0.00005))
        gpu_rate = float(rates.get("gpu_second_usd", 0.00120))
        egress_rate = float(rates.get("egress_gb_usd", 0.090))

        for event in events:
            endpoint = str(event.get("endpoint", "unknown"))
            latency_ms = float(event.get("latency_ms", 0.0))
            output_bytes = int(event.get("output_bytes", 0))
            input_bytes = int(event.get("input_bytes", 0))
            used_gpu = bool(event.get("used_gpu", False))

            by_endpoint[endpoint] += 1
            total_latency_ms += latency_ms
            total_input += input_bytes
            total_output += output_bytes

            seconds = max(0.0, latency_ms / 1000.0)
            if used_gpu:
                gpu_count += 1
                gpu_runtime_usd += seconds * gpu_rate
            else:
                inference_compute_usd += seconds * cpu_rate

            egress_usd += (output_bytes / (1024.0**3)) * egress_rate

        summary = {
            "events": len(events),
            "by_endpoint": dict(sorted(by_endpoint.items())),
            "avg_latency_ms": round(total_latency_ms / max(1, len(events)), 6),
            "total_input_bytes": total_input,
            "total_output_bytes": total_output,
            "gpu_requests": gpu_count,
            "estimated_costs_usd": {
                "inference_compute_usd": round(inference_compute_usd, 6),
                "gpu_runtime_usd": round(gpu_runtime_usd, 6),
                "egress_usd": round(egress_usd, 6),
            },
        }

        alerts = []
        for key, amount in summary["estimated_costs_usd"].items():
            budget_value = float(budgets.get(key, 0.0))
            if budget_value <= 0:
                continue
            pct = (float(amount) / budget_value) * 100.0
            level = None
            if pct >= critical_pct:
                level = "critical"
            elif pct >= warning_pct:
                level = "warning"
            if level:
                alerts.append({"metric": key, "value": amount, "budget": budget_value, "percent": round(pct, 2), "level": level})

        summary["alerts"] = alerts
        return summary
