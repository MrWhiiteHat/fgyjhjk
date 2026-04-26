"""Prediction distribution and confidence drift detection."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List


def _extract_predictions(records: Iterable[Dict[str, object]]) -> tuple[List[str], List[float]]:
    labels: List[str] = []
    probabilities: List[float] = []
    for record in records:
        label = str(record.get("predicted_label", "")).upper().strip()
        if label:
            labels.append(label)
        try:
            prob = float(record.get("predicted_probability", record.get("probability", 0.0)))
            if math.isfinite(prob):
                probabilities.append(max(0.0, min(1.0, prob)))
        except (TypeError, ValueError):
            continue
    return labels, probabilities


def _distribution(labels: List[str]) -> Dict[str, float]:
    if not labels:
        return {}
    total = len(labels)
    counts: Dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return {label: count / total for label, count in counts.items()}


def _histogram(values: List[float], bins: int = 10) -> List[float]:
    if not values:
        return [0.0] * bins
    counts = [0] * bins
    for value in values:
        idx = min(bins - 1, max(0, int(value * bins)))
        counts[idx] += 1
    total = sum(counts)
    return [count / total for count in counts]


def _l1_distance(dist_a: List[float], dist_b: List[float]) -> float:
    return sum(abs(a - b) for a, b in zip(dist_a, dist_b))


class PredictionDriftDetector:
    """Compares live predictions with baseline for class and confidence drift."""

    def __init__(self, collapse_ratio_threshold: float = 0.95) -> None:
        self.collapse_ratio_threshold = float(collapse_ratio_threshold)

    def compare(
        self,
        reference_records: List[Dict[str, object]],
        current_records: List[Dict[str, object]],
    ) -> Dict[str, object]:
        ref_labels, ref_probs = _extract_predictions(reference_records)
        cur_labels, cur_probs = _extract_predictions(current_records)

        ref_dist = _distribution(ref_labels)
        cur_dist = _distribution(cur_labels)

        all_labels = sorted(set(ref_dist.keys()) | set(cur_dist.keys()))
        class_shift = {
            label: round(float(cur_dist.get(label, 0.0) - ref_dist.get(label, 0.0)), 6)
            for label in all_labels
        }

        ref_hist = _histogram(ref_probs)
        cur_hist = _histogram(cur_probs)
        confidence_shift = _l1_distance(ref_hist, cur_hist) / 2.0

        dominant_class = ""
        dominant_ratio = 0.0
        for label, ratio in cur_dist.items():
            if ratio > dominant_ratio:
                dominant_class = label
                dominant_ratio = ratio

        collapse_detected = dominant_ratio >= self.collapse_ratio_threshold and len(cur_labels) >= 50

        label_distance = sum(abs(class_shift.get(label, 0.0)) for label in all_labels) / 2.0
        drift_score = max(label_distance, confidence_shift)

        if collapse_detected or drift_score >= 0.25:
            alert_level = "critical"
        elif drift_score >= 0.15:
            alert_level = "warning"
        else:
            alert_level = "none"

        return {
            "method": "prediction_distribution_shift",
            "reference_count": len(ref_labels),
            "current_count": len(cur_labels),
            "reference_distribution": ref_dist,
            "current_distribution": cur_dist,
            "class_balance_change": class_shift,
            "confidence_hist_reference": ref_hist,
            "confidence_hist_current": cur_hist,
            "confidence_distribution_shift": round(confidence_shift, 6),
            "label_distribution_shift": round(label_distance, 6),
            "drift_score": round(drift_score, 6),
            "collapse_detected": bool(collapse_detected),
            "dominant_class": dominant_class,
            "dominant_ratio": round(dominant_ratio, 6),
            "alert_level": alert_level,
        }
