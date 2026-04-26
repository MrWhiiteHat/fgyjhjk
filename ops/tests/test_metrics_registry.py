from ops.monitoring.metrics_registry import MetricSpec, MetricsRegistry


def test_metrics_registry_defaults_and_updates():
    registry = MetricsRegistry()

    assert registry.has_metric("request_count")
    assert registry.has_metric("request_latency_ms")

    labels = {"endpoint": "/predict", "status_code": "200", "environment": "test", "model_version": "v1"}
    registry.inc("request_count", labels=labels)
    registry.observe("request_latency_ms", 100.0, labels=labels)
    registry.observe("request_latency_ms", 200.0, labels=labels)
    registry.observe("request_latency_ms", 300.0, labels=labels)

    registry.update_latency_percentiles(labels=labels)

    exported = registry.export()
    assert "metrics" in exported
    assert "p95_latency" in exported["metrics"]

    p95 = registry.percentile("request_latency_ms", 95.0, labels=labels)
    p99 = registry.percentile("request_latency_ms", 99.0, labels=labels)
    assert p95 >= 200.0
    assert p99 >= p95


def test_metrics_registry_duplicate_spec_guard():
    registry = MetricsRegistry()
    spec = MetricSpec("custom_counter", "counter", "Custom counter", ("label",))
    registry.register_metric(spec)

    # Same spec is idempotent.
    registry.register_metric(spec)

    bad_spec = MetricSpec("custom_counter", "gauge", "Different kind", ("label",))
    try:
        registry.register_metric(bad_spec)
        assert False, "Expected ValueError for conflicting metric spec"
    except ValueError:
        assert True
