# Trust Boundaries

## Boundary 1: Client Device -> Backend API

Untrusted side:
- Uploaded files and metadata.
- Claimed MIME types and optional client hints.
- Repeated query patterns and threshold parameters.

Trusted side:
- API validation logic.
- Authn/authz and tenant routing controls.
- Input firewall and abuse response policies.

Controls:
- Strict media validation and malformed blocking.
- Upload size and count limits.
- Query cadence and pattern anomaly detection.

## Boundary 2: Backend API -> Model Runtime

Untrusted side:
- Preprocessed tensors originating from user uploads.

Trusted side:
- Defensive preprocessing and perturbation scoring.
- Uncertainty gate and response shaping policy.
- Ensemble fallback checker when configured.

Controls:
- Adversarial precheck and perturbation detector before final response confidence.
- High-risk response minimization.

## Boundary 3: Model Artifacts -> Secure Loader

Untrusted side:
- Artifact binaries from storage or release channels.

Trusted side:
- Integrity verification and signature policy.
- Approved-version and blocklist enforcement.

Controls:
- Checksum verification.
- Optional signature verification.
- Strict-mode load denial on verification failure.

## Boundary 4: Feedback Store -> Retraining Dataset Builder

Untrusted side:
- User-submitted corrections and labels.

Trusted side:
- Sanitization, anomaly filtering, consistency checks, quarantine process.
- Retraining guard approval policy.

Controls:
- Duplicate and burst detection.
- Label consistency checks.
- Provenance requirement and anomaly thresholds.

## Boundary 5: Report Export Path

Untrusted side:
- User-selected export parameters.

Trusted side:
- Output minimizer and explanation redaction rules.

Controls:
- Limit sensitive internals in exports under suspicious risk.
- Restrict precision and avoid raw logits where policy requires.

## Assumptions

- Storage ACLs are correctly configured.
- Secret management for signatures and policy config is controlled.
- Logging backends are immutable enough for forensic utility.

## Limitations

- Boundary controls mitigate but do not eliminate all zero-day payload classes.
- Cross-service enforcement quality depends on consistent deployment configuration.
