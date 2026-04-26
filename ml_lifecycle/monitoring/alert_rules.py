"""Alert rule evaluation for lifecycle monitoring events."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Alert:
    """Alert payload for lifecycle notifications."""

    alert_type: str
    severity: str
    message: str
    details: dict[str, str] = field(default_factory=dict)


class AlertRules:
    """Threshold-driven alert generator for lifecycle stages."""

    def __init__(
        self,
        *,
        data_drift_threshold: float = 0.2,
        confidence_shift_threshold: float = 0.1,
        error_rate_delta_threshold: float = 0.05,
    ) -> None:
        self.data_drift_threshold = float(data_drift_threshold)
        self.confidence_shift_threshold = float(confidence_shift_threshold)
        self.error_rate_delta_threshold = float(error_rate_delta_threshold)

    def evaluate_drift(self, *, data_drift_score: float, confidence_shift: float, error_rate_delta: float | None) -> list[Alert]:
        """Emit drift alerts when thresholds are exceeded."""

        alerts: list[Alert] = []
        if data_drift_score >= self.data_drift_threshold:
            alerts.append(
                Alert(
                    alert_type="drift_detected",
                    severity="high",
                    message="Data drift threshold exceeded",
                    details={"data_drift_score": f"{data_drift_score:.6f}"},
                )
            )
        if confidence_shift >= self.confidence_shift_threshold:
            alerts.append(
                Alert(
                    alert_type="drift_detected",
                    severity="medium",
                    message="Concept drift confidence shift threshold exceeded",
                    details={"confidence_shift": f"{confidence_shift:.6f}"},
                )
            )
        if error_rate_delta is not None and error_rate_delta >= self.error_rate_delta_threshold:
            alerts.append(
                Alert(
                    alert_type="drift_detected",
                    severity="critical",
                    message="Concept drift error-rate delta threshold exceeded",
                    details={"error_rate_delta": f"{error_rate_delta:.6f}"},
                )
            )
        return alerts

    @staticmethod
    def retraining_triggered(reason: str) -> Alert:
        """Create retraining trigger alert."""

        return Alert(
            alert_type="retraining_triggered",
            severity="high",
            message="Retraining pipeline triggered",
            details={"reason": reason},
        )

    @staticmethod
    def failed_validation(details: str) -> Alert:
        """Create validation failure alert."""

        return Alert(
            alert_type="failed_validation",
            severity="critical",
            message="Candidate model failed validation",
            details={"reason": details},
        )

    @staticmethod
    def failed_rollout(details: str) -> Alert:
        """Create rollout failure alert."""

        return Alert(
            alert_type="failed_rollout",
            severity="critical",
            message="Rollout failed and rollback may be required",
            details={"reason": details},
        )
