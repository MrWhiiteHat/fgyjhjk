"""Output minimizer for extraction-resistant response shaping."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


@dataclass
class OutputPolicy:
    """Policy definition for output detail levels."""

    detail_level: str = "standard"
    probability_decimals: int = 4
    expose_logits: bool = False
    expose_rich_explanations: bool = False
    expose_per_frame_details: bool = False


class OutputMinimizer:
    """Minimizes output detail while retaining valid product utility."""

    def apply(self, *, response_payload: dict, policy: OutputPolicy, suspicious_context: bool = False) -> dict:
        """Apply full, standard, or restricted response detail policy."""

        payload = deepcopy(response_payload)
        level = str(policy.detail_level).lower().strip()
        if suspicious_context and level == "full":
            level = "standard"
        if suspicious_context and level == "standard":
            level = "restricted"

        data = payload.get("data")
        if not isinstance(data, dict):
            payload["data"] = {"security_policy": level}
            return payload

        prediction = data.get("prediction") if isinstance(data.get("prediction"), dict) else None
        if prediction:
            if "predicted_probability" in prediction:
                decimals = 6 if level == "full" else (policy.probability_decimals if level == "standard" else 2)
                prediction["predicted_probability"] = round(float(prediction["predicted_probability"]), decimals)

            if level == "restricted" or not policy.expose_logits:
                if "predicted_logit" in prediction:
                    prediction["predicted_logit"] = None
                prediction["logit_exposed"] = False
            else:
                prediction["logit_exposed"] = True

        if level == "restricted" or not policy.expose_rich_explanations:
            if "explainability" in data:
                data["explainability"] = {
                    "status": "limited",
                    "reason": "output_minimizer_policy",
                }

        if level != "full" and "per_frame" in data and not policy.expose_per_frame_details:
            per_frame = data.get("per_frame")
            if isinstance(per_frame, list):
                data["per_frame"] = per_frame[: min(3, len(per_frame))]
                data["per_frame_limited"] = True

        data["security_output_policy"] = level
        payload["data"] = data
        return payload
