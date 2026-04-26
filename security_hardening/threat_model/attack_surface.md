# Attack Surface

## External Entry Points

- Image inference endpoint.
- Video inference endpoint.
- Bulk/folder/zip inference endpoints.
- Explainability endpoint.
- Feedback submission endpoint.
- Report export endpoint.
- Model lifecycle and release control endpoints (internal/admin).

## Attack Vectors

### Input and Evasion

- Malformed image/video payloads.
- MIME-extension mismatch payload smuggling.
- Archive bombs or traversal names.
- Extreme dimensions and adversarial patch placement.
- Compression and noise perturbations aimed at decision flips.

### API Abuse

- Bulk query storms and high-cadence scraping.
- Parameter fishing (threshold exploration and confidence probing).
- Token sharing across clients to evade simple per-user limits.

### Explainability Abuse

- Requesting high-detail overlays to infer model focus and weaknesses.
- Repeated explanation requests for near-duplicate samples.
- Extraction of sensitive internals via verbose diagnostics.

### Feedback and Retraining Poisoning

- Coordinated duplicate corrections.
- Improbable systematic label flips.
- Bursty submissions from single actor or subnet.
- Low-quality/no-provenance feedback aimed at retraining admission.

### Artifact and Deployment Supply Chain

- Tampered model binary with modified behavior.
- Replay of older vulnerable model versions.
- Attempted promotion without passing security and robustness gate.

## Data and Control Plane Surfaces

- Model registry and artifact store.
- Feedback store and quarantine workflow.
- Monitoring event pipeline and alert routing.
- Release orchestration and emergency disable controls.

## Mitigation Mapping

- Input guard, upload firewall, archive guard.
- Perturbation detector, adversarial precheck, uncertainty gate.
- Query pattern detector, rate-shape guard, output minimizer.
- Feedback sanitizer, anomaly filter, retraining guard.
- Artifact integrity verifier, signature verifier, secure loader, security gate.
