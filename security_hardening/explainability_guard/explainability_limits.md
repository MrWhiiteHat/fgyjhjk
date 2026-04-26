# Explainability Limits

This module applies policy-based guardrails for explainability outputs.

## Honest Limitations

- Explainability is not a direct security proof.
- Redacted overlays and summaries can reduce forensic depth for end users.
- Under elevated risk, explanation detail is intentionally reduced to avoid aiding extraction.

## Policy Outcomes

- `full`: allowed only for low-risk contexts and permitted plans.
- `standard`: default mode with sensitive internals removed.
- `redacted`: high-risk mode with heavily reduced detail.
- `none`: explanation denied when risk is too high.

## Display Safety

Overlay output is constrained by:

- bounded dimensions,
- bounded transparency,
- aspect ratio sanity checks.

## Security Principle

When risk is elevated, the system prefers conservative explanation outputs over detailed introspection.
