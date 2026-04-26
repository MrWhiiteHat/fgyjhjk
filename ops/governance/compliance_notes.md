# Compliance Notes

## Baseline Controls
- Access control via API keys and role gating for admin actions.
- Structured audit logging for model/promotion/rollback/security-sensitive operations.
- Security headers and input validation enforced at API boundary.
- Integrity checks (checksum/hash chaining) for artifacts and audit events.

## Operational Evidence
- Deployment history in immutable append-only JSONL.
- Drift and health reports archived with timestamps.
- Release checklist completion records retained with each promotion.

## Recommended Mapping (Informational)
- SOC 2 CC6/CC7: Access controls, logging, monitoring, change management.
- ISO 27001 A.12/A.16: Operations security, incident management.
- Internal AI governance: model cards, risk register, rollback preparedness.

## Gaps to Track
- Formal key-rotation cadence and secrets vault integration.
- Periodic restore drill evidence archive.
- Automated policy-as-code enforcement in CI gates.
