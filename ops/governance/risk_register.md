# Risk Register

| ID | Risk | Category | Likelihood | Impact | Detection Signal | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R-001 | Model drift over time | Model | Medium | High | Drift score and alert rules | Automated drift checks + rollback readiness | ML Team | Open |
| R-002 | Class collapse (single-class predictions) | Model | Medium | High | Prediction distribution monitor | Class-collapse detector + gated deploy | ML Team | Open |
| R-003 | API abuse / request flooding | Security | Medium | High | Rate-limit and abuse detector | Throttling, API keys, WAF rules | Platform | Open |
| R-004 | Artifact tampering | Security | Low | High | Checksum mismatch | Hash verification and immutable storage controls | Platform | Open |
| R-005 | Failed deployment promotes bad model | Operations | Medium | High | Validation gate failures, incident alerts | Approval workflow + staged promotion + rollback | MLOps | Open |
| R-006 | Backup corruption | Reliability | Low | High | Backup verification failures | Automated verify and periodic restore drills | Platform | Open |
| R-007 | Cost overrun from storage/inference growth | FinOps | Medium | Medium | Budget threshold alerts | Usage tracking + policy-based cleanup | Ops | Open |
| R-008 | Insufficient audit trail | Compliance | Low | High | Missing audit records | Mandatory audit logger and retention policy | Security | Open |
