# System Threat Model

## Scope

This threat model covers the Real vs Fake Face Detection platform across inference, explainability, feedback intake, retraining, model artifact loading, SaaS multi-tenant API controls, and lifecycle release gates.

Integrated modules:

- Module 4 (inference and evaluation): runtime inference and explainability generation.
- Module 5 (backend and frontend): API surface and client-visible responses.
- Module 6 (monitoring and MLOps): operational logging, abuse monitoring, and alerting hooks.
- Module 8 (cloud SaaS controls): tenant identity, API key routing, idempotency, and quota signals.
- Module 9 (lifecycle and retraining): drift, feedback, retraining triggers, validation, and rollout.

## Assets

- Model artifacts and metadata.
- Inference endpoints and response contracts.
- Explainability outputs.
- Feedback and corrected label store.
- Retraining datasets and training pipeline outputs.
- Security event stream and alert channels.
- Tenant isolation boundaries and plan controls.

## Adversary Types

- Opportunistic attacker: sends malformed media or abuse traffic to bypass checks.
- Capability attacker: performs adversarial perturbations and black-box probing.
- Resource abuser: exploits free-tier or bulk endpoints for scraping or extraction.
- Poisoning actor: submits coordinated malicious feedback to degrade future models.
- Insider or supply-chain actor: attempts artifact tampering or vulnerable model promotion.

## Attacker Goals

- Evade fake detection by manipulating input content.
- Degrade model quality through poisoned feedback and retraining data.
- Extract decision boundaries or confidence behavior via probing.
- Abuse explainability details to reverse-engineer weak points.
- Exhaust quota and inference capacity through bulk abuse.
- Promote or load tampered/vulnerable model artifacts.

## Threat Priorities

- High: artifact integrity failure, poisoning admission, unsafe release promotion.
- High: extraction probing with sustained near-duplicate queries.
- Medium to high: adversarial perturbation and evasion attempts.
- Medium: explainability misuse and overexposure of internals.
- Medium: endpoint abuse and archive-based payload abuse.

## Defense-in-Depth Strategy

1. Input path controls:
- Validate MIME-extension alignment and media structure.
- Apply adversarial precheck and perturbation scoring before high-confidence responses.

2. Output controls:
- Minimize confidence precision and hide raw logits for suspicious contexts.
- Redact explanation payload details under elevated risk.

3. Feedback and retraining controls:
- Sanitize, deduplicate, and quarantine suspicious feedback.
- Block insecure retraining batches with provenance or skew issues.

4. Artifact and release controls:
- Verify checksum and optional signature in secure loader.
- Enforce approved-version and vulnerable-version policy.
- Block release through security gate when robustness or integrity checks fail.

5. Monitoring and response:
- Emit structured security events by category and severity.
- Route alerts to ops hooks and incident classifier.
- Use emergency disable and rollback triggers for fast containment.

## Assumptions

- TLS termination and baseline API authentication exist in deployment.
- Clock synchronization is reasonable for event-time analysis.
- Tenancy context from Module 8 is available where multi-tenant enforcement is required.
- Module 9 lifecycle hooks are available for retraining guard integration.
- Storage backends preserve artifact bytes without silent modification.

## Limitations

- Adversarial defenses are heuristic and probabilistic; no perfect detection guarantee.
- Signature verification in this module supports shared-secret HMAC style unless external PKI is integrated.
- Query pattern detection quality depends on request history retention and granularity.
- Red-team resilience depends on periodically updated perturbation suites and attack policies.
