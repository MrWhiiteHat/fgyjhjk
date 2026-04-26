"""Prometheus integration for central metrics registry."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from ops.monitoring.metrics_registry import MetricSpec, MetricsRegistry, get_metrics_registry

try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
except Exception:  # noqa: BLE001
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    CollectorRegistry = None
    Counter = None
    Gauge = None
    Histogram = None
    generate_latest = None


@dataclass
class PrometheusMetricObjects:
    """Container for generated prometheus client metric objects."""

    counter: Dict[str, object]
    gauge: Dict[str, object]
    histogram: Dict[str, object]


class PrometheusMetrics:
    """Bridge between in-memory registry and Prometheus exporter."""

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        enabled: bool = True,
        environment: str = "production",
    ) -> None:
        self.registry = registry or get_metrics_registry()
        self.enabled = bool(enabled)
        self.environment = str(environment)
        self.available = bool(self.enabled and CollectorRegistry and Counter and Gauge and Histogram and generate_latest)
        self.prom_registry = CollectorRegistry(auto_describe=True) if self.available else None
        self.prom = PrometheusMetricObjects(counter={}, gauge={}, histogram={})
        if self.available:
            self._sync_registry_specs()

    @staticmethod
    def _prom_name(name: str) -> str:
        if name.startswith("app_"):
            return name
        return f"app_{name}"

    def _sync_registry_specs(self) -> None:
        exported = self.registry.export()["metrics"]
        for metric_name, payload in exported.items():
            spec_payload = payload["spec"]
            spec = MetricSpec(
                name=str(spec_payload["name"]),
                kind=str(spec_payload["kind"]),
                description=str(spec_payload["description"]),
                labels=tuple(spec_payload.get("labels", [])),
            )
            self._register_prometheus_metric(spec)

    def _register_prometheus_metric(self, spec: MetricSpec) -> None:
        if not self.available:
            return

        prom_name = self._prom_name(spec.name)
        labelnames = list(spec.labels)

        if spec.kind == "counter" and spec.name not in self.prom.counter:
            self.prom.counter[spec.name] = Counter(prom_name, spec.description, labelnames=labelnames, registry=self.prom_registry)
        elif spec.kind == "gauge" and spec.name not in self.prom.gauge:
            self.prom.gauge[spec.name] = Gauge(prom_name, spec.description, labelnames=labelnames, registry=self.prom_registry)
        elif spec.kind == "histogram" and spec.name not in self.prom.histogram:
            self.prom.histogram[spec.name] = Histogram(prom_name, spec.description, labelnames=labelnames, registry=self.prom_registry)

    def inc(self, metric_name: str, amount: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        self.registry.inc(metric_name, amount=amount, labels=labels)
        if self.available and metric_name in self.prom.counter:
            metric = self.prom.counter[metric_name]
            metric.labels(**{key: str(labels.get(key, "")) for key in metric._labelnames}).inc(float(amount))

    def set(self, metric_name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        self.registry.set(metric_name, value=value, labels=labels)
        if self.available and metric_name in self.prom.gauge:
            metric = self.prom.gauge[metric_name]
            metric.labels(**{key: str(labels.get(key, "")) for key in metric._labelnames}).set(float(value))

    def observe(self, metric_name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        self.registry.observe(metric_name, value=value, labels=labels)
        if self.available and metric_name in self.prom.histogram:
            metric = self.prom.histogram[metric_name]
            metric.labels(**{key: str(labels.get(key, "")) for key in metric._labelnames}).observe(float(value))

    def track_request(
        self,
        endpoint: str,
        status_code: int,
        model_version: str,
        latency_ms: float,
    ) -> None:
        labels_common = {
            "endpoint": str(endpoint),
            "status_code": str(status_code),
            "environment": self.environment,
        }
        self.inc("request_count", labels=labels_common)
        self.observe(
            "request_latency_ms",
            value=float(latency_ms),
            labels={
                "endpoint": str(endpoint),
                "model_version": str(model_version),
                "environment": self.environment,
            },
        )
        self.registry.update_latency_percentiles(labels={"endpoint": str(endpoint), "environment": self.environment})
        p99 = self.registry.percentile("request_latency_ms", 99.0, labels={"endpoint": str(endpoint), "model_version": str(model_version), "environment": self.environment})
        self.set("app_latency_p99_ms", p99, labels={"endpoint": str(endpoint), "environment": self.environment})
        if int(status_code) >= 400:
            self.inc("error_count", labels=labels_common)

    @contextmanager
    def timed(
        self,
        endpoint: str,
        model_version: str,
        status_code_provider: Callable[[], int] | None = None,
    ):
        """Context manager for request timing and metric update."""
        started = time.perf_counter()
        status_code = 200
        try:
            yield
        except Exception:
            status_code = 500
            raise
        finally:
            if status_code_provider is not None:
                status_code = int(status_code_provider())
            duration_ms = (time.perf_counter() - started) * 1000.0
            self.track_request(
                endpoint=endpoint,
                status_code=status_code,
                model_version=model_version,
                latency_ms=duration_ms,
            )

    def timed_function(
        self,
        endpoint: str,
        model_version_getter: Callable[..., str] | None = None,
        status_code_getter: Callable[[object], int] | None = None,
    ):
        """Decorator for timing function execution and emitting request metrics."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                started = time.perf_counter()
                status_code = 200
                try:
                    result = func(*args, **kwargs)
                    if status_code_getter is not None:
                        status_code = int(status_code_getter(result))
                    return result
                except Exception:
                    status_code = 500
                    raise
                finally:
                    model_version = model_version_getter(*args, **kwargs) if model_version_getter else "unknown"
                    duration_ms = (time.perf_counter() - started) * 1000.0
                    self.track_request(endpoint=endpoint, status_code=status_code, model_version=model_version, latency_ms=duration_ms)

            return wrapper

        return decorator

    def render_latest(self) -> tuple[bytes, str]:
        """Return prometheus-formatted metrics payload and content type."""
        if self.available and self.prom_registry is not None and generate_latest is not None:
            return generate_latest(self.prom_registry), CONTENT_TYPE_LATEST

        snapshot = self.registry.export()
        lines = ["# Prometheus disabled or unavailable, returning compatibility text"]
        for metric_name, payload in snapshot.get("metrics", {}).items():
            spec = payload.get("spec", {})
            lines.append(f"# HELP {self._prom_name(metric_name)} {spec.get('description', '')}")
            lines.append(f"# TYPE {self._prom_name(metric_name)} {spec.get('kind', 'gauge')}")
            for value in payload.get("values", []):
                labels = value.get("labels", {})
                if labels:
                    labels_text = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{self._prom_name(metric_name)}{{{labels_text}}} {value.get('value', 0)}")
                else:
                    lines.append(f"{self._prom_name(metric_name)} {value.get('value', 0)}")
        return ("\n".join(lines) + "\n").encode("utf-8"), "text/plain; charset=utf-8"

    def build_fastapi_metrics_handler(self):
        """Build FastAPI-compatible async endpoint handler for metrics."""

        async def handler():
            payload, content_type = self.render_latest()
            return {
                "content": payload,
                "content_type": content_type,
            }

        return handler
