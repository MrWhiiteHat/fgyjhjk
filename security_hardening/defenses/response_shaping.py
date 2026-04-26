"""Response shaping to reduce sensitive exposure under suspicious conditions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


@dataclass
class ResponseShapingConfig:
    """Policy settings for output minimization and precision reduction."""

    suppress_logits_on_risk: bool = True
    explanation_risk_threshold: float = 0.6
    restricted_precision_decimals: int = 3


class ResponseShaper:
    """Shapes API response while preserving contract-compatible structure."""

    def __init__(self, config: ResponseShapingConfig | None = None) -> None:
        self.config = config or ResponseShapingConfig()

    def shape(
        self,
        *,
        response_payload: dict,
        risk_score: float,
        suspicious: bool,
        policy_level: str = "standard",
    ) -> dict:
        """Apply response shaping without breaking top-level schema fields."""

        payload = deepcopy(response_payload)
        data = payload.get("data")
        if not isinstance(data, dict):
            return payload

        level = str(policy_level).lower().strip()
        if suspicious and level == "full":
            level = "standard"
        if suspicious and risk_score >= 0.75:
            level = "restricted"

        prediction = data.get("prediction") if isinstance(data.get("prediction"), dict) else None
        if prediction is not None:
            if "predicted_probability" in prediction:
                prediction["predicted_probability"] = round(
                    float(prediction["predicted_probability"]),
                    self.config.restricted_precision_decimals if level != "full" else 6,
                )

            if self.config.suppress_logits_on_risk and risk_score >= 0.5 and "predicted_logit" in prediction:
                prediction["predicted_logit"] = None
                prediction["logit_suppressed"] = True

            if level == "restricted":
                prediction["confidence_statement"] = "review_recommended"
                if "model_name" in prediction:
                    prediction["model_name"] = "secured"

        if risk_score >= self.config.explanation_risk_threshold and "explainability" in data:
            data["explainability"] = {
                "status": "suppressed_due_to_risk",
                "reason": "security_policy",
            }

        data["security"] = {
            "policy_level": level,
            "risk_score": round(float(risk_score), 6),
            "review_recommended": bool(suspicious or risk_score >= 0.6),
        }
        payload["data"] = data
        return payload
