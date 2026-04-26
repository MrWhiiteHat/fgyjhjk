# Module 6: Monitoring + Security + MLOps + Production Operations

This document describes how to operate the production operations layer implemented under `ops/`.

## 1. Scope

Module 6 includes:
- Monitoring and observability
- Security controls
- MLOps lifecycle management
- Reliability safeguards
- Governance and operational runbooks
- CI/CD pipeline templates
- Backup and restore management
- Cost tracking and budget alerting
- Operations scripts and tests

## 2. Directory Map

- `ops/configs/`: central ops configuration files
- `ops/monitoring/`: health, latency, drift orchestration, metrics, Prometheus bridge
- `ops/security/`: auth, rate-limit, input/content validation, security headers, abuse heuristics
- `ops/logging/`: structured app logs, audit logs, retention cleanup
- `ops/mlops/`: model metadata, registry, validation gate, promotions, rollbacks
- `ops/reliability/`: circuit breaker, retries, timeout, queue and resource guards
- `ops/backups/`: backup policy, backup manager, restore manager, verification
- `ops/cost/`: usage/storage/GPU trackers, inference estimator, budget policy
- `ops/governance/`: model card template, risk register, release and incident runbooks
- `ops/ci_cd/`: GitHub Actions workflow templates, deploy scripts, env templates
- `ops/scripts/`: CLI utilities for day-to-day operations
- `ops/tests/`: unit tests for core operations behavior

## 3. Bootstrap and Initialization

Run once per environment:

```bash
python ops/scripts/bootstrap_ops.py
```

This creates required directories and initializes MLOps state files.

## 4. Runtime Safeguards

### Security
- API key authentication with role checks in `ops/security/auth.py`
- Sliding-window request throttling in `ops/security/rate_limit.py`
- Path and archive traversal protection in `ops/security/input_sanitizer.py`
- Content extension/mime/size/dimension validation in `ops/security/content_validation.py`
- Response hardening headers in `ops/security/security_headers.py`
- Heuristic abuse profiling in `ops/security/abuse_detection.py`

### Reliability
- Dependency isolation via circuit breaker
- Bounded retry and timeout wrappers
- Queue overflow and stale request controls
- Resource pressure checks (CPU/memory/disk/GPU)
- Graceful degradation mode selection under stress

### Monitoring
- In-memory metric registry and optional Prometheus bridge
- Health monitor with periodic snapshots
- Drift monitor with feature/prediction/quality analysis and report generation
- Alert rules and Grafana dashboard templates included under `ops/monitoring/`

## 5. MLOps Lifecycle

### Register model metadata

```bash
python ops/scripts/register_model.py \
  --model-name real_fake_detector \
  --model-version v1.0.0 \
  --artifact-path training/outputs/checkpoints/real_fake_baseline/best_model.pt \
  --dataset-name preprocessed_v1
```

### Promote model

```bash
python ops/scripts/promote_model.py \
  --model-version v1.0.0 \
  --target-stage staging \
  --actor mlops \
  --reason "staging validation"
```

```bash
python ops/scripts/promote_model.py \
  --model-version v1.0.0 \
  --target-stage production \
  --actor release_manager \
  --reason "approved release" \
  --approval-token ticket-123
```

### Rollback deployment

```bash
python ops/scripts/rollback_deployment.py \
  --target-version v0.9.4 \
  --actor oncall \
  --reason "post-release regression"
```

## 6. Drift and Health Operations

Run one-off health audit:

```bash
python ops/scripts/run_health_audit.py --output ops/reports/health_audit.json
```

Run one-off drift check:

```bash
python ops/scripts/run_drift_check.py \
  --config ops/configs/drift_config.yaml \
  --records ops/drift/state/current_records.json \
  --model-version v1.0.0
```

## 7. Backup and Recovery

Create backup:

```bash
python ops/scripts/run_backup.py --policy ops/backups/backup_policy.yaml --tier daily
```

Restore backup:

```bash
python ops/scripts/restore_backup.py \
  --archive ops/backups/archives/backup_daily_YYYYMMDDTHHMMSSZ.zip \
  --restore-root ops/backups/restore
```

Verify archive manually:

```bash
python ops/backups/verify_backup.py ops/backups/archives/backup_daily_YYYYMMDDTHHMMSSZ.zip
```

## 8. Cost and Budget Tracking

- Use `ops/cost/usage_tracker.py` to record request-level usage events and cost alerts.
- Use `ops/cost/storage_tracker.py` for storage footprint and monthly storage-cost estimation.
- Use `ops/cost/gpu_utilization.py` for periodic GPU usage sampling.
- Use `ops/cost/inference_cost_estimator.py` for per-request and batch cost estimates.
- Budget thresholds and rates are configured in `ops/cost/budget_alerts.yaml`.

## 9. CI/CD Templates

Workflow templates are provided in `ops/ci_cd/github_actions/`:
- `backend_ci.yml`
- `frontend_ci.yml`
- `model_validation.yml`
- `docker_publish.yml`
- `deploy.yml`

Deploy scripts are in `ops/ci_cd/scripts/` and environment templates are in `ops/ci_cd/environments/`.

## 10. Validation Commands

Run operations tests:

```bash
pytest -q ops/tests
```

Recommended release minimum:

```bash
pytest -q ops/tests/test_metrics_registry.py \
  ops/tests/test_audit_logger.py \
  ops/tests/test_rate_limit.py \
  ops/tests/test_model_registry.py \
  ops/tests/test_drift_monitor.py \
  ops/tests/test_backup_restore.py \
  ops/tests/test_reliability_guards.py
```

## 11. Governance and On-Call Playbook

Before production promotion:
- Complete `ops/governance/release_checklist.md`
- Update `ops/governance/risk_register.md`
- Generate and review model card

During incidents:
- Execute `ops/governance/incident_runbook.md`
- If needed, execute `ops/governance/rollback_runbook.md`

Data retention and compliance references:
- `ops/governance/data_retention_policy.md`
- `ops/governance/compliance_notes.md`

## 12. Notes

- In-memory controls (rate limiter, abuse tracker, metric process state) are process-local by design.
- For multi-replica production, pair these modules with shared infra controls (centralized cache, distributed limiter, external metrics backend).
- Keep configs under `ops/configs/` as the source of truth for policy thresholds and operational behavior.
