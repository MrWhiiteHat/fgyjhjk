"""Operational health monitor with periodic snapshots."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from typing import Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml


@dataclass
class HealthCheck:
    """Single health check outcome entry."""

    name: str
    ok: bool
    severity: str
    details: Dict[str, object] = field(default_factory=dict)


@dataclass
class HealthSnapshot:
    """Snapshot containing full runtime health state."""

    timestamp: str
    state: str
    checks: List[HealthCheck]

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


class HealthMonitor:
    """Performs service, model, and resource health checks."""

    def __init__(self, monitoring_config_path: str = "ops/configs/monitoring_config.yaml") -> None:
        self.monitoring_config_path = Path(monitoring_config_path)
        self.config = self._load_config(self.monitoring_config_path)
        self.health_history_path = Path(
            str(self.config.get("health_history_path", "app/backend/outputs/ops/health/health_history.jsonl"))
        )
        self.health_history_path.parent.mkdir(parents=True, exist_ok=True)

        self.backend_health_url = str(self.config.get("backend_health_url", "http://127.0.0.1:8000/api/v1/health"))
        self.temp_dir = Path(str(self.config.get("temp_dir", "app/backend/tmp")))
        self.output_dir = Path(str(self.config.get("output_dir", "app/backend/outputs")))
        self.model_registry_path = Path(str(self.config.get("model_registry_path", "ops/mlops/state/model_registry.json")))
        self.require_gpu = bool(self.config.get("require_gpu", False))

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _directory_size_bytes(path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def _check_backend_alive(self) -> HealthCheck:
        request = Request(self.backend_health_url, headers={"User-Agent": "ops-health-monitor/1.0"})
        try:
            with urlopen(request, timeout=3.0) as response:  # noqa: S310
                status = int(response.getcode())
                ok = 200 <= status < 300
                return HealthCheck(
                    name="backend_alive",
                    ok=ok,
                    severity="critical",
                    details={"url": self.backend_health_url, "status": status},
                )
        except URLError as exc:
            return HealthCheck(
                name="backend_alive",
                ok=False,
                severity="critical",
                details={"url": self.backend_health_url, "error": str(exc)},
            )

    def _check_model_loaded(self) -> HealthCheck:
        if not self.model_registry_path.exists():
            return HealthCheck(
                name="model_loaded",
                ok=False,
                severity="critical",
                details={"reason": "model registry file missing", "registry": str(self.model_registry_path)},
            )

        try:
            with self.model_registry_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            return HealthCheck(
                name="model_loaded",
                ok=False,
                severity="critical",
                details={"reason": "unable to read model registry", "error": str(exc)},
            )

        active_version = str(payload.get("active_model_version", "")).strip()
        models = payload.get("models", {})
        metadata = models.get(active_version, {}) if isinstance(models, dict) else {}
        artifact_path = Path(str(metadata.get("artifact_path", "")))
        ok = bool(active_version and artifact_path.exists())
        return HealthCheck(
            name="model_loaded",
            ok=ok,
            severity="critical",
            details={
                "active_model_version": active_version,
                "artifact_path": str(artifact_path),
                "artifact_exists": artifact_path.exists(),
            },
        )

    def _check_disk_usage(self) -> HealthCheck:
        disk_path = self.output_dir if self.output_dir.exists() else Path(".")
        usage = shutil.disk_usage(disk_path)
        used_percent = (usage.used / usage.total) * 100.0 if usage.total > 0 else 0.0
        ok = used_percent < 95.0
        severity = "warning" if used_percent >= 85.0 else "info"
        return HealthCheck(
            name="disk_usage",
            ok=ok,
            severity=severity,
            details={
                "path": str(disk_path),
                "used_percent": round(used_percent, 2),
                "free_gb": round(usage.free / (1024**3), 2),
            },
        )

    def _check_temp_usage(self) -> HealthCheck:
        temp_size_bytes = self._directory_size_bytes(self.temp_dir)
        temp_size_gb = temp_size_bytes / (1024**3)
        ok = temp_size_gb < 5.0
        severity = "warning" if temp_size_gb >= 3.0 else "info"
        return HealthCheck(
            name="temp_dir_usage",
            ok=ok,
            severity=severity,
            details={
                "path": str(self.temp_dir),
                "size_gb": round(temp_size_gb, 3),
            },
        )

    def _check_output_writable(self) -> HealthCheck:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        marker = self.output_dir / ".ops_health_write_test"
        try:
            marker.write_text("ok", encoding="utf-8")
            marker.unlink(missing_ok=True)
            return HealthCheck(
                name="output_writable",
                ok=True,
                severity="critical",
                details={"path": str(self.output_dir)},
            )
        except OSError as exc:
            return HealthCheck(
                name="output_writable",
                ok=False,
                severity="critical",
                details={"path": str(self.output_dir), "error": str(exc)},
            )

    def _check_gpu(self) -> HealthCheck:
        if not self.require_gpu:
            return HealthCheck(name="gpu_available", ok=True, severity="info", details={"required": False})
        try:
            import torch

            available = bool(torch.cuda.is_available())
            return HealthCheck(
                name="gpu_available",
                ok=available,
                severity="warning",
                details={"required": True, "available": available},
            )
        except Exception as exc:  # noqa: BLE001
            return HealthCheck(
                name="gpu_available",
                ok=False,
                severity="warning",
                details={"required": True, "error": str(exc)},
            )

    def run_health_checks(self) -> HealthSnapshot:
        """Run all health checks and return a classified snapshot."""
        checks = [
            self._check_backend_alive(),
            self._check_model_loaded(),
            self._check_disk_usage(),
            self._check_temp_usage(),
            self._check_output_writable(),
            self._check_gpu(),
        ]

        critical_failed = any((not check.ok and check.severity == "critical") for check in checks)
        warning_failed = any((not check.ok and check.severity == "warning") for check in checks)

        if critical_failed:
            state = "unhealthy"
        elif warning_failed:
            state = "degraded"
        else:
            state = "healthy"

        return HealthSnapshot(timestamp=self._now_iso(), state=state, checks=checks)

    def save_snapshot(self, snapshot: HealthSnapshot) -> None:
        line = json.dumps(snapshot.to_dict(), sort_keys=True)
        with self.health_history_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def run_once(self) -> HealthSnapshot:
        snapshot = self.run_health_checks()
        self.save_snapshot(snapshot)
        return snapshot

    def run_periodic(self, stop_event: Event, max_iterations: int | None = None) -> List[HealthSnapshot]:
        """Run periodic checks until stop event is set."""
        interval = max(1, int(self.config.get("health_check_interval_sec", 60)))
        snapshots: List[HealthSnapshot] = []
        iterations = 0

        while not stop_event.is_set():
            snapshot = self.run_once()
            snapshots.append(snapshot)
            iterations += 1
            if max_iterations is not None and iterations >= int(max_iterations):
                break
            stop_event.wait(interval)

        return snapshots
