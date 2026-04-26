# Red Team Checklist

## Input Evasion

- [ ] Test malformed headers and MIME-extension mismatch payloads.
- [ ] Test extreme dimensions and unusual aspect ratios.
- [ ] Test adversarial patch-like perturbations.

## Extraction

- [ ] Perform near-duplicate probing against confidence outputs.
- [ ] Perform threshold-fishing sweeps.
- [ ] Perform bulk enumeration and cadence attacks.

## Poisoning

- [ ] Submit coordinated duplicate corrections.
- [ ] Submit bursty low-confidence corrections.
- [ ] Submit missing-provenance feedback and verify quarantine.

## Artifact Security

- [ ] Verify checksum mismatch blocks secure loader.
- [ ] Verify blocklisted model versions are denied.
- [ ] Verify strict mode denies unverifiable signatures when enabled.

## Rollout Safety

- [ ] Verify security gate blocks unsafe candidate release.
- [ ] Verify emergency disable controls for explainability and bulk endpoints.
- [ ] Verify rollback triggers activate under post-release attack surge.
