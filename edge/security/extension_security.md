# Browser Extension Security Guidance

## Principle of Least Privilege
- Keep host permissions scoped to required domains.
- Avoid blanket permissions where optional permissions can be requested at runtime.

## Content Script Safety
- Never execute untrusted page scripts.
- Scan only image media types and enforce scan limits.
- Avoid sending raw page content unless user explicitly enables backend fallback.

## Data Storage
- Use `chrome.storage.local` for settings and bounded history.
- Avoid persistence of sensitive raw media by default.

## Messaging Hardening
- Validate message origin and payload schema between popup/background/content.
- Use explicit action enums, reject unknown commands.

## Abuse Controls
- Debounce repeated scans.
- Avoid rescanning identical URLs repeatedly.
