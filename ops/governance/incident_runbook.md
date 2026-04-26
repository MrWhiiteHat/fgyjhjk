# Incident Runbook

## 1. Trigger Conditions
- Sustained 5xx spike above threshold.
- Latency SLO breach for p95/p99.
- Model drift or class collapse critical alert.
- Security incident (abuse burst, auth anomalies, tamper suspicion).

## 2. Immediate Actions
1. Declare incident severity and owner.
2. Capture timeline start and active model version.
3. Enable protective controls (tight rate limits, safe mode).
4. Freeze non-essential deployments.

## 3. Triage
1. Validate service health monitor status.
2. Inspect logs and audit trail for correlated errors.
3. Identify whether root cause is model, infrastructure, or abuse.
4. Estimate blast radius and user impact.

## 4. Containment
1. If model-related, execute rollback runbook.
2. If infra-related, apply reliability degradation mode.
3. If security-related, rotate keys and block offending clients.

## 5. Recovery
1. Confirm metrics stabilize and alerts clear.
2. Return service to normal mode gradually.
3. Communicate status update and closure criteria.

## 6. Postmortem
1. Publish incident summary within 24 hours.
2. Include root cause, contributing factors, and corrective actions.
3. Track follow-up tasks to closure.
