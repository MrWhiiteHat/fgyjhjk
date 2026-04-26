# On-Device Explainability Limits

## What Is Implemented
- Lightweight confidence-region visualization based on image gradient energy.
- Overlay rendering for user-facing preview in constrained environments.

## What Is Not Claimed
- No full Grad-CAM attribution is claimed for all runtime/model combinations.
- No guarantee of causal explanation from heuristic heatmaps.

## Why Limits Exist
- Mobile/browser inference runtimes often do not expose full intermediate tensors/gradients.
- Battery, memory, and latency constraints make heavy explainability impractical on-device.

## Safe Product Behavior
- Display explicit label: "heuristic on-device visualization".
- Offer backend explanation fallback when connectivity and permissions permit.
- Preserve privacy-mode behavior: skip backend explainability if privacy mode blocks sync/upload.

## Validation Guidance
- Compare on-device overlays with backend explainability for qualitative drift checks.
- Track user trust messaging in UI to avoid overconfidence.
