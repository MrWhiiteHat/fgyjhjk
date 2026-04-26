"""Sensitive field redaction for explainability payloads."""

from __future__ import annotations

from copy import deepcopy


class ExplanationRedactor:
    """Redacts sensitive internal diagnostics from explanation payloads."""

    SENSITIVE_KEYS = {
        "raw_gradients",
        "intermediate_activations",
        "layer_response_map",
        "token_level_saliency",
        "debug_internal",
    }

    def redact(self, *, explanation_payload: dict, mode: str) -> dict:
        """Redact payload according to explanation mode."""

        payload = deepcopy(explanation_payload)
        normalized = str(mode).lower().strip()

        if normalized == "full":
            return payload

        if normalized in {"standard", "redacted"}:
            for key in list(payload.keys()):
                if key in self.SENSITIVE_KEYS:
                    payload.pop(key, None)

            if normalized == "redacted":
                payload["detail_reduction"] = "high"
                if "heatmap_values" in payload:
                    payload.pop("heatmap_values", None)
                if "feature_attribution_scores" in payload:
                    payload.pop("feature_attribution_scores", None)
            else:
                payload["detail_reduction"] = "moderate"
            return payload

        return {
            "status": "explanation_suppressed",
            "reason": "policy_mode_none",
        }
