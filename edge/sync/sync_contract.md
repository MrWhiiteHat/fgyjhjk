# Sync Contract

## Purpose
Define the canonical protocol between edge clients (mobile/extension) and backend sync APIs.

## Required Event Fields
- event_id
- created_at
- media_type
- media_sha256
- predicted_label
- predicted_probability
- model_version
- model_source
- threshold
- privacy_mode

## Status Lifecycle
`pending -> syncing -> synced`

Error paths:
- `pending -> syncing -> failed`
- `pending -> syncing -> conflict`

## Deduplication
A client must deduplicate queued records by:
`media_sha256 + model_version + threshold + media_type`

## Privacy Behavior
- `strict_local`: no automatic backend sync.
- `user_selectable`: sync allowed only when user enables it.
- `extension_minimum_retention`: minimal metadata retention, no raw media persistence.

## Conflict Resolution
Supported strategies:
- `client_wins`
- `server_wins`
- `latest_timestamp` (default)

## Retry and Backoff
- Exponential backoff with jitter.
- Bounded max attempts before conflict state.

## Backend Expectations
Backend should expose a signed/authenticated endpoint (for example `/api/v1/sync/events`) with idempotent writes by `event_id`.

## Security Notes
- Validate signatures/API keys per Module 6 auth policy.
- Reject malformed payloads with clear error codes.
- Preserve audit trail of sync writes and conflict resolutions.
