# Abuse Cases

## Case A: Adversarial Evasion Image

Scenario:
- Attacker submits a face image with localized patch perturbations to force a fake sample to appear real.

Signals:
- High-frequency anomaly surge.
- Localized patch score elevated.
- Ensemble disagreement increased.

Response:
- Mark sample as suspicious.
- Suppress high-confidence claims.
- Flag for review and emit perturbation alert.

## Case B: Threshold Fishing for Model Extraction

Scenario:
- Attacker repeatedly submits near-identical inputs while sweeping threshold and observing confidence changes.

Signals:
- Near-duplicate digest pattern.
- High threshold variability in short window.
- Confidence probing distribution signatures.

Response:
- Apply output minimizer (restricted policy).
- Throttle or block with abuse response policy.
- Emit extraction suspicion alert.

## Case C: Poisoned Feedback Campaign

Scenario:
- Coordinated accounts submit bursty label corrections flipping consistent samples.

Signals:
- Duplicate coordinated feedback clusters.
- Improbable label flip ratio.
- Missing provenance and low confidence scores.

Response:
- Quarantine suspicious records.
- Exclude from retraining candidate batch.
- Emit poisoning suspected event.

## Case D: Artifact Tampering

Scenario:
- Modified model artifact is introduced into release path.

Signals:
- Checksum mismatch or signature verify failure.
- Version appears on vulnerable model blocklist.

Response:
- Secure loader blocks artifact.
- Security gate fails release.
- Trigger rollback and incident alert.

## Case E: Free-Tier Bulk Abuse

Scenario:
- Automated actor drives high-volume bulk endpoint usage to scrape outputs.

Signals:
- Rate-shape anomalies.
- Endpoint-specific quota and file-count limit hits.

Response:
- Throttle, then block if persistent.
- Alert route to operations.
- Tenant-aware abuse scoring for SaaS enforcement.

## Case F: Explainability Endpoint Abuse

Scenario:
- Repeated requests aim to extract rich overlays and internals for reverse engineering.

Signals:
- Elevated attack score and repeated explanation requests.
- Query pattern extraction indicators.

Response:
- Explanation policy denies or redacts internals.
- Overlay safety rules reduce detail.
- Record event for incident classification.

## Assumptions and Limits

- Abuse classification is probabilistic and may require manual review.
- Some high-skill adversarial techniques can evade heuristic detectors.
- Rate limits can be bypassed by broad botnets without upstream network controls.
