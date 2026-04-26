"""Resource pressure guard for CPU, memory, disk, and optional GPU checks."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class ResourceSnapshot:
    """Current system resource utilization metrics."""

    timestamp: str
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float
    gpu_percent: float | None


class ResourceGuard:
    """Evaluates resource pressure using configurable utilization thresholds."""

    def __init__(
        self,
        cpu_threshold: float = 90.0,
        memory_threshold: float = 90.0,
        disk_threshold: float = 90.0,
        gpu_threshold: float = 95.0,
        disk_path: str = ".",
    ) -> None:
        self.cpu_threshold = float(cpu_threshold)
        self.memory_threshold = float(memory_threshold)
        self.disk_threshold = float(disk_threshold)
        self.gpu_threshold = float(gpu_threshold)
        self.disk_path = Path(disk_path)

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def collect_snapshot(self) -> ResourceSnapshot:
        cpu_percent = None
        memory_percent = None

        try:
            import psutil

            cpu_percent = float(psutil.cpu_percent(interval=0.1))
            memory_percent = float(psutil.virtual_memory().percent)
        except Exception:  # noqa: BLE001
            pass

        usage = shutil.disk_usage(self.disk_path)
        disk_percent = (usage.used / max(1, usage.total)) * 100.0

        gpu_percent = None
        try:
            import torch

            if torch.cuda.is_available():
                # Approximate GPU memory utilization across device 0.
                total = float(torch.cuda.get_device_properties(0).total_memory)
                allocated = float(torch.cuda.memory_allocated(0))
                gpu_percent = (allocated / max(1.0, total)) * 100.0
        except Exception:  # noqa: BLE001
            pass

        return ResourceSnapshot(
            timestamp=self._now_iso(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=float(disk_percent),
            gpu_percent=gpu_percent,
        )

    def evaluate(self) -> Dict[str, object]:
        snapshot = self.collect_snapshot()
        breaches = []

        if snapshot.cpu_percent is not None and snapshot.cpu_percent >= self.cpu_threshold:
            breaches.append("cpu")
        if snapshot.memory_percent is not None and snapshot.memory_percent >= self.memory_threshold:
            breaches.append("memory")
        if snapshot.disk_percent >= self.disk_threshold:
            breaches.append("disk")
        if snapshot.gpu_percent is not None and snapshot.gpu_percent >= self.gpu_threshold:
            breaches.append("gpu")

        return {
            "snapshot": {
                "timestamp": snapshot.timestamp,
                "cpu_percent": snapshot.cpu_percent,
                "memory_percent": snapshot.memory_percent,
                "disk_percent": snapshot.disk_percent,
                "gpu_percent": snapshot.gpu_percent,
            },
            "breaches": breaches,
            "under_pressure": len(breaches) > 0,
        }

    def assert_safe(self) -> None:
        status = self.evaluate()
        if status["under_pressure"]:
            raise RuntimeError(f"Resource pressure detected: {status['breaches']}")
