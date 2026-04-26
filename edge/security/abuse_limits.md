# Abuse Limits

## Mobile
- Enforce per-session detection caps in low-power mode.
- Rate limit backend fallback requests.

## Extension
- Respect scan limit per page.
- Debounce auto-scan actions.
- Block unsupported or oversized assets.

## Sync
- Queue max size and max retries to prevent infinite loops.
- Validate payload schema before enqueue.

## Backend Integration
- Apply Module 6 auth + rate-limit + abuse detection policies to edge sync and fallback endpoints.
