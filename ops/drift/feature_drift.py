"""Numeric feature drift detection using PSI and KS distance."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List


def _to_float_list(values: Iterable[object]) -> List[float]:
    output: List[float] = []
    for value in values:
        try:
            if value is None:
                continue
            numeric = float(value)
            if math.isfinite(numeric):
                output.append(numeric)
        except (TypeError, ValueError):
            continue
    return output


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    q = max(0.0, min(1.0, float(q)))
    rank = q * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    frac = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * frac


def _build_bins(reference: List[float], bins: int) -> List[float]:
    if not reference:
        return [0.0, 1.0]
    unique = sorted(set(reference))
    if len(unique) == 1:
        value = unique[0]
        return [value - 1.0, value + 1.0]

    bin_edges = [_percentile(reference, i / bins) for i in range(bins + 1)]
    # ensure monotonic growth
    cleaned = [bin_edges[0]]
    for edge in bin_edges[1:]:
        if edge <= cleaned[-1]:
            edge = cleaned[-1] + 1e-9
        cleaned.append(edge)
    return cleaned


def _histogram(values: List[float], bin_edges: List[float]) -> List[float]:
    if not values:
        return [0.0 for _ in range(len(bin_edges) - 1)]
    counts = [0 for _ in range(len(bin_edges) - 1)]
    for value in values:
        placed = False
        for idx in range(len(bin_edges) - 1):
            left = bin_edges[idx]
            right = bin_edges[idx + 1]
            last = idx == len(bin_edges) - 2
            if (left <= value < right) or (last and value <= right):
                counts[idx] += 1
                placed = True
                break
        if not placed and value < bin_edges[0]:
            counts[0] += 1
        elif not placed:
            counts[-1] += 1

    total = sum(counts)
    if total == 0:
        return [0.0 for _ in counts]
    return [count / total for count in counts]


def population_stability_index(reference: List[float], current: List[float], bins: int = 10) -> float:
    """Compute PSI between reference and current numeric samples."""
    if not reference or not current:
        return 0.0
    edges = _build_bins(reference, bins=bins)
    ref_dist = _histogram(reference, edges)
    cur_dist = _histogram(current, edges)

    eps = 1e-8
    score = 0.0
    for ref_p, cur_p in zip(ref_dist, cur_dist):
        ref_safe = max(ref_p, eps)
        cur_safe = max(cur_p, eps)
        score += (cur_safe - ref_safe) * math.log(cur_safe / ref_safe)
    return float(score)


def ks_statistic(reference: List[float], current: List[float]) -> float:
    """Compute two-sample Kolmogorov-Smirnov distance without scipy dependency."""
    if not reference or not current:
        return 0.0

    ref = sorted(reference)
    cur = sorted(current)
    i = j = 0
    d_max = 0.0

    while i < len(ref) and j < len(cur):
        value = ref[i] if ref[i] <= cur[j] else cur[j]
        while i < len(ref) and ref[i] <= value:
            i += 1
        while j < len(cur) and cur[j] <= value:
            j += 1
        cdf_ref = i / len(ref)
        cdf_cur = j / len(cur)
        d_max = max(d_max, abs(cdf_ref - cdf_cur))

    return float(d_max)


class FeatureDriftDetector:
    """Runs per-feature drift analysis over numeric metadata."""

    def __init__(self, psi_threshold: float = 0.2, ks_threshold: float = 0.2, bins: int = 10) -> None:
        self.psi_threshold = float(psi_threshold)
        self.ks_threshold = float(ks_threshold)
        self.bins = int(bins)

    def compare(
        self,
        reference_records: List[Dict[str, object]],
        current_records: List[Dict[str, object]],
        features: List[str],
    ) -> Dict[str, object]:
        """Compare feature distributions for current window vs reference."""
        per_feature: List[Dict[str, object]] = []

        for feature in features:
            ref_values = _to_float_list(record.get(feature) for record in reference_records)
            cur_values = _to_float_list(record.get(feature) for record in current_records)

            if len(ref_values) < 10 or len(cur_values) < 10:
                per_feature.append(
                    {
                        "feature": feature,
                        "status": "insufficient_data",
                        "reference_count": len(ref_values),
                        "current_count": len(cur_values),
                        "psi": 0.0,
                        "ks": 0.0,
                        "drift_detected": False,
                    }
                )
                continue

            psi_score = population_stability_index(ref_values, cur_values, bins=self.bins)
            ks_score = ks_statistic(ref_values, cur_values)
            drift_detected = psi_score >= self.psi_threshold or ks_score >= self.ks_threshold

            per_feature.append(
                {
                    "feature": feature,
                    "status": "ok",
                    "reference_count": len(ref_values),
                    "current_count": len(cur_values),
                    "psi": round(psi_score, 6),
                    "ks": round(ks_score, 6),
                    "drift_detected": bool(drift_detected),
                    "method": "psi+ks",
                }
            )

        scored = [item for item in per_feature if item.get("status") == "ok"]
        overall = 0.0
        if scored:
            overall = sum(max(float(item["psi"]), float(item["ks"])) for item in scored) / len(scored)

        return {
            "method": "feature_drift_psi_ks",
            "feature_count": len(features),
            "evaluated_count": len(scored),
            "overall_drift_score": round(overall, 6),
            "drift_detected": any(bool(item.get("drift_detected", False)) for item in scored),
            "per_feature": per_feature,
            "thresholds": {
                "psi_threshold": self.psi_threshold,
                "ks_threshold": self.ks_threshold,
            },
        }
