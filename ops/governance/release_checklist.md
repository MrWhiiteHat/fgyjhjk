# Release Checklist

## Pre-Release
- [ ] Training run completed and reports generated.
- [ ] Model metadata registered with checksum and dataset lineage.
- [ ] Validation gate checks passed (metrics + artifact + smoke test).
- [ ] Security checks enabled (auth, rate limit, sanitizer, headers).
- [ ] Monitoring dashboards and alert rules reviewed.
- [ ] Rollback candidate confirmed.
- [ ] Backup policy executed and latest backup verified.

## Release Approval
- [ ] Required approver(s) reviewed model card.
- [ ] Risk register reviewed for unresolved high risks.
- [ ] Deployment window approved by operations owner.

## Deployment
- [ ] Promote to `staging` and run sanity checks.
- [ ] Promote to `production` with tracked deployment event.
- [ ] Inference cache invalidation confirmed.

## Post-Release
- [ ] Latency/error/throughput/drift monitored for 30+ minutes.
- [ ] No critical alerts fired after deployment.
- [ ] Incident channel notified of successful rollout.
- [ ] Release notes archived with deployment tracker entry.
