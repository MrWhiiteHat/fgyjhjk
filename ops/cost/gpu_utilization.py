"""GPU utilization sampling utilities for cost and capacity tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class GpuSample:
    """Single GPU utilization sample."""

    timestamp: str
    util_percent: float
    memory_util_percent: float


class GpuUtilizationTracker:
    """Collects approximate GPU utilization samples.

    Preference order:
    1) pynvml (if available)
    2) torch memory utilization approximation
    """

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def sample(self) -> GpuSample | None:
        # Preferred path: NVML for true utilization metrics.
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = float(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)
            mem_util = float(pynvml.nvmlDeviceGetUtilizationRates(handle).memory)
            pynvml.nvmlShutdown()
            return GpuSample(timestamp=self._now_iso(), util_percent=util, memory_util_percent=mem_util)
        except Exception:  # noqa: BLE001
            pass

        # Fallback path: approximate via torch memory allocation.
        try:
            import torch

            if not torch.cuda.is_available():
                return None
            total = float(torch.cuda.get_device_properties(0).total_memory)
            used = float(torch.cuda.memory_allocated(0))
            mem_util = (used / max(1.0, total)) * 100.0
            return GpuSample(timestamp=self._now_iso(), util_percent=mem_util, memory_util_percent=mem_util)
        except Exception:  # noqa: BLE001
            return None

    def sample_window(self, sample_count: int = 5, interval_seconds: float = 1.0) -> Dict[str, object]:
        samples: List[GpuSample] = []
        for _ in range(max(1, int(sample_count))):
            sample = self.sample()
            if sample is not None:
                samples.append(sample)
            time.sleep(max(0.0, float(interval_seconds)))

        if not samples:
            return {
                "available": False,
                "samples": [],
                "avg_util_percent": None,
                "avg_memory_util_percent": None,
            }

        avg_util = sum(item.util_percent for item in samples) / len(samples)
        avg_mem = sum(item.memory_util_percent for item in samples) / len(samples)

        return {
            "available": True,
            "samples": [
                {
                    "timestamp": item.timestamp,
                    "util_percent": round(item.util_percent, 6),
                    "memory_util_percent": round(item.memory_util_percent, 6),
                }
                for item in samples
            ],
            "avg_util_percent": round(avg_util, 6),
            "avg_memory_util_percent": round(avg_mem, 6),
        }
