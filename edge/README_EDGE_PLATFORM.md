# Module 7 Edge Platform

This module delivers the end-to-end edge platform layer with four deployment surfaces:
- On-device inference runtime and conversion utilities
- Mobile app client for image/video/camera detection
- Browser extension for page-level scan overlays
- Offline queue and synchronization contracts

## Directory Map
- `on_device/`: preprocessing, runtimes, model conversion, explainability, and edge configs.
- `mobile/app/`: Expo React Native app with hooks/services/screens/components for local/backend detection workflows.
- `browser_extension/`: Manifest V3 extension with popup/options/content/background architecture.
- `sync/`: offline queue, protocol contracts, conflict handling, and upload scheduler.
- `security/`: privacy, permissions, and hardening guidance.
- `deployment/`: app store, release, monitoring, rollback, and SLA templates/checklists.
- `tests/`: module-level verification for sync, extension scan logic, config constraints, and storage contract checks.

## Edge Behavior Guarantees
- Local-first inference is configurable with backend fallback modes.
- Privacy mode gates synchronization behavior.
- Offline operation captures prediction history and queue state.
- Sync protocol uses deterministic dedupe keys and lifecycle status transitions.
- Browser extension scanning respects candidate filters and configurable scan limits.

## Validation Coverage
- Runtime wrapper behavior and preprocessing equivalence tests.
- Quantized/reference probability consistency tests.
- Benchmark utility contract tests.
- Sync protocol and queue transition tests.
- Extension scan logic and mobile storage contract tests.
- Config shape/range validation tests.

## Integration Notes
- Backend endpoints expected by edge clients should follow Module 5 API contracts.
- Keep model versions and normalization constants synchronized between training outputs and edge configs.
- Verify each deployment target independently during release readiness checks.
