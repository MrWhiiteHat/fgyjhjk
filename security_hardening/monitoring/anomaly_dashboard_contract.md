# Anomaly Dashboard Contract

## Purpose

Defines the minimum schema for security anomaly dashboards consuming events from `security_events.py` and `attack_monitor.py`.

## Event Stream Schema

Required fields:

- event_id
- timestamp
- category
- severity
- source
- message

Optional identity fields:

- tenant_id
- user_id
- ip

Optional metadata object for category-specific dimensions.

## Core Panels

1. Category trend panel:
- malformed_input
- perturbation_suspected
- poisoning_suspected
- extraction_suspected
- artifact_integrity_failure

2. Severity trend panel:
- low
- medium
- high
- critical

3. Top entities panel:
- top tenant_id by event volume
- top user_id by event volume
- top ip by event volume

4. Surge detection panel:
- categories where count >= configured surge threshold per window.

## Alerting Integration

Dashboard should consume `AlertRouter` outputs and map routed alerts to:

- ops channel,
- security incident queue,
- audit archive.

## Retention Guidance

- Keep raw events for forensic retention window.
- Keep aggregated metrics for long-term trend analysis.
