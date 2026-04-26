# Model Protection Notes

## Goals
- Limit unauthorized extraction and tampering of on-device artifacts.

## Controls
- Ship checksummed model artifacts with version manifest.
- Validate hash before loading runtime.
- Prefer quantized/runtime-specific artifacts over full training checkpoints.
- Keep model files in app-private directories where possible.

## Limitations
- Client-side artifact extraction cannot be fully prevented on compromised devices.
- Focus on tamper detection, monitoring, and rapid model rotation.

## Operational Practices
- Track model version adoption across mobile and extension clients.
- Rotate models via signed update channel tied to Module 6 MLOps governance.
