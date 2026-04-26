# Security Policy for RealFake Production Operations

## Scope

This policy governs API inference endpoints, administrative control plane actions, model lifecycle operations, and artifact/report access.

## Core Controls

1. Authentication
- API key authentication is required when enabled by configuration.
- Administrative operations require elevated role (`admin` or `platform`).
- Deny-by-default is enforced for admin routes when authentication is enabled.

2. Authorization
- Public inference endpoints map to `public` role.
- Model promotion, rollback, and registry mutation require admin role.

3. Request Protection
- Rate limiting is enforced per IP or API key with structured error responses.
- Abuse heuristics detect malformed bursts, oversize attempts, and repeated upload failures.

4. Input and Content Validation
- Filenames are sanitized before storage.
- Allowed extension and MIME type checks are mandatory.
- Archive extraction blocks traversal attempts and nested-archive abuse.
- Image/video content is validated for readable dimensions and size constraints.

5. Secrets Handling
- Secrets are loaded only from environment variables or mounted secret files.
- No secret values are hardcoded or emitted in clear text logs.
- Secret-bearing fields are redacted in structured logs.

6. Logging and Audit
- Structured logs include request and model context.
- Sensitive administrative actions are written to hash-chained audit records.
- Audit logs are retained separately from application logs.

7. Response Hardening
- Security headers are applied to reduce content sniffing, framing abuse, and leakage.

## Operational Expectations

- Security configuration is environment-specific and reviewed before production deployment.
- Any increase in suspicious activity must be escalated through incident runbook procedures.
- Rollback authority must be restricted to approved operators only.
