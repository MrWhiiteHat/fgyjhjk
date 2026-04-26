# Rollback Runbook

## Preconditions
- Deployment tracker available.
- Candidate model version exists in registry.
- On-call owner and approver notified.

## Rollback Steps
1. Identify current active version and impact window.
2. List rollback candidates from recent successful production deployments.
3. Select target version with known-good health profile.
4. Execute rollback operation with reason and actor attribution.
5. Verify active model version switched in registry/config.
6. Invalidate prediction caches if enabled.
7. Observe key health/latency/error metrics for stabilization.

## Validation After Rollback
- [ ] Error rate returns below threshold.
- [ ] Prediction distribution normalizes.
- [ ] No security or drift critical alerts remain.
- [ ] Audit event recorded for rollback action.

## Communication
- Notify stakeholders with target version and rationale.
- Record incident linkage and final status.
