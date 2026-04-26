# Watermarking Notes (Design-Only)

This module does not claim a production watermark implementation.

## Objective

Explore optional defensive watermarking ideas that can help detect model extraction and unauthorized redistribution of model responses.

## Candidate Approaches

1. Response-space watermarking:
- Introduce tiny, controlled response perturbations for selected canary requests.
- Track whether those perturbation signatures appear in cloned systems.

2. Input-trigger watermarking:
- Maintain hidden trigger samples whose expected outputs are known only to internal teams.
- Use trigger validation to evaluate suspicious third-party models.

3. Traceable explanation markers:
- Add non-sensitive, policy-controlled markers in explanation metadata that help correlate leaked outputs.

## Constraints

- Must not materially degrade core user experience.
- Must not create safety regressions or privacy leakage.
- Must remain disabled by default unless explicitly approved.

## Current Status

- Documented concept only.
- No active runtime watermark logic in this module.
