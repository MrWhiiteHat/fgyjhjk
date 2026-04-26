# Secure Release Checklist

## Artifact Security

- [ ] Artifact checksum verified.
- [ ] Signature verification passed if enabled.
- [ ] Model version not blocklisted.

## Robustness and Security Validation

- [ ] Perturbation suite benchmark executed.
- [ ] Security regression tests passed.
- [ ] Extraction risk policy satisfied.
- [ ] Poisoning controls configured and active.

## Deployment Safety

- [ ] Security gate result is PASS.
- [ ] Rollback triggers configured.
- [ ] Emergency disable controls verified.
- [ ] Incident routing endpoints verified.

## Post-Release Monitoring

- [ ] Attack monitor dashboard active.
- [ ] Alert routing and escalation verified.
- [ ] On-call response runbook reviewed.
