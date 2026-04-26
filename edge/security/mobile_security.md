# Mobile Security Guidance

## Data Handling
- Validate media extension, mime type, and size before processing.
- Store transient media in app-scoped storage only.
- Remove temporary files immediately after inference where possible.

## Authentication
- Use short-lived backend tokens/API keys.
- Do not hardcode secrets in source bundles.
- Keep auth material in secure storage (platform keystore/keychain wrappers).

## Inference Integrity
- Verify local model checksum before load.
- Log model version used for each prediction event.

## Offline Queue Safety
- Encrypt queue storage when platform capabilities allow.
- Respect privacy mode by disabling sync when strict local mode is active.

## Network Security
- Require HTTPS for backend traffic in production.
- Pin certificates where feasible.
