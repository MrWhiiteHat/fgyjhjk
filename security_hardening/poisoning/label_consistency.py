"""Label consistency checks for repeated feedback on the same prediction."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LabelConsistencyResult:
    """Result for consistency analysis across repeated sample labels."""

    inconsistent_prediction_ids: list[str] = field(default_factory=list)
    improbable_flip_prediction_ids: list[str] = field(default_factory=list)
    per_prediction_stats: dict[str, dict[str, float]] = field(default_factory=dict)


class LabelConsistencyChecker:
    """Detects label inconsistency and improbable flips across repeated corrections."""

    def evaluate(
        self,
        *,
        feedback_records: list[dict],
        inconsistency_threshold: float = 0.40,
        improbable_flip_ratio_threshold: float = 0.70,
    ) -> LabelConsistencyResult:
        """Evaluate consistency signals from grouped feedback records."""

        grouped: dict[str, list[dict]] = {}
        for record in feedback_records:
            prediction_id = str(record.get("prediction_id", "")).strip()
            if not prediction_id:
                continue
            grouped.setdefault(prediction_id, []).append(record)

        inconsistent: list[str] = []
        improbable_flips: list[str] = []
        stats: dict[str, dict[str, float]] = {}

        for prediction_id, records in grouped.items():
            labels = [record.get("corrected_label") for record in records if record.get("corrected_label") is not None]
            labels = [int(label) for label in labels if int(label) in {0, 1}]
            if not labels:
                continue

            ones = sum(1 for label in labels if label == 1)
            zeros = len(labels) - ones
            majority = 1 if ones >= zeros else 0
            minority = len(labels) - max(ones, zeros)
            inconsistency_ratio = minority / max(len(labels), 1)

            predicted_labels = [record.get("predicted_label") for record in records if record.get("predicted_label") is not None]
            predicted_labels = [int(label) for label in predicted_labels if int(label) in {0, 1}]
            if predicted_labels:
                opposite_count = sum(1 for label in labels if label != predicted_labels[0])
                flip_ratio = opposite_count / len(labels)
            else:
                flip_ratio = 0.0

            stats[prediction_id] = {
                "count": float(len(labels)),
                "majority_label": float(majority),
                "inconsistency_ratio": float(inconsistency_ratio),
                "flip_ratio": float(flip_ratio),
            }

            if inconsistency_ratio >= float(inconsistency_threshold):
                inconsistent.append(prediction_id)
            if flip_ratio >= float(improbable_flip_ratio_threshold):
                improbable_flips.append(prediction_id)

        return LabelConsistencyResult(
            inconsistent_prediction_ids=sorted(set(inconsistent)),
            improbable_flip_prediction_ids=sorted(set(improbable_flips)),
            per_prediction_stats=stats,
        )
