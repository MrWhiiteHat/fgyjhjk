"""Incident classifier for security event severity harmonization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IncidentClassification:
    """Normalized incident classification output."""

    category: str
    severity: str
    incident_type: str


class IncidentClassifier:
    """Maps event categories and risk to actionable incident types."""

    CATEGORY_MAP = {
        "malformed_input": "input_attack",
        "perturbation_suspected": "adversarial_attack",
        "poisoning_suspected": "training_data_attack",
        "extraction_suspected": "model_extraction",
        "artifact_integrity_failure": "supply_chain",
    }

    def classify(self, *, category: str, risk_score: float) -> IncidentClassification:
        """Classify category into severity and incident type."""

        c = str(category).strip().lower()
        risk = float(min(max(risk_score, 0.0), 1.0))

        if risk >= 0.85:
            severity = "critical"
        elif risk >= 0.65:
            severity = "high"
        elif risk >= 0.35:
            severity = "medium"
        else:
            severity = "low"

        incident_type = self.CATEGORY_MAP.get(c, "unknown_security_event")
        return IncidentClassification(category=c, severity=severity, incident_type=incident_type)
