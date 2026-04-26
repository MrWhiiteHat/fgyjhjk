"""Data drift detection using feature distribution divergence metrics."""

from __future__ import annotations

import math


def _safe_histogram(values: list[float], min_value: float, max_value: float, bins: int) -> list[float]:
    if bins <= 0:
        raise ValueError("bins must be > 0")
    if min_value == max_value:
        max_value = min_value + 1.0

    width = (max_value - min_value) / bins
    counts = [0] * bins
    for value in values:
        idx = int((value - min_value) / width)
        if idx < 0:
            idx = 0
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1

    total = max(sum(counts), 1)
    return [count / total for count in counts]


def kl_divergence(p: list[float], q: list[float], eps: float = 1e-9) -> float:
    """Compute KL divergence D(P || Q) for discrete distributions."""

    if len(p) != len(q):
        raise ValueError("Distribution lengths must match")

    total = 0.0
    for left, right in zip(p, q):
        pl = max(float(left), eps)
        qr = max(float(right), eps)
        total += pl * math.log(pl / qr)
    return total


def population_stability_index(expected: list[float], actual: list[float], eps: float = 1e-9) -> float:
    """Compute PSI score between expected and actual distributions."""

    if len(expected) != len(actual):
        raise ValueError("Distribution lengths must match")

    psi = 0.0
    for exp_val, act_val in zip(expected, actual):
        e = max(float(exp_val), eps)
        a = max(float(act_val), eps)
        psi += (a - e) * math.log(a / e)
    return psi


def compare_feature_distributions(
    reference: list[dict[str, float]],
    current: list[dict[str, float]],
    bins: int = 10,
) -> dict[str, dict[str, float]]:
    """Compare per-feature distributions and return KL/PSI drift metrics."""

    if not reference or not current:
        raise ValueError("reference and current feature sets are required")

    feature_names = sorted(set(reference[0].keys()) | set(current[0].keys()))
    output: dict[str, dict[str, float]] = {}

    for feature in feature_names:
        ref_values = [float(item.get(feature, 0.0)) for item in reference]
        cur_values = [float(item.get(feature, 0.0)) for item in current]

        min_value = min(ref_values + cur_values)
        max_value = max(ref_values + cur_values)

        ref_dist = _safe_histogram(ref_values, min_value=min_value, max_value=max_value, bins=bins)
        cur_dist = _safe_histogram(cur_values, min_value=min_value, max_value=max_value, bins=bins)

        kl = kl_divergence(ref_dist, cur_dist)
        psi = population_stability_index(ref_dist, cur_dist)
        output[feature] = {
            "kl_divergence": kl,
            "psi": psi,
            "drift_score": max(kl, psi),
        }

    return output


def aggregate_data_drift(feature_drift: dict[str, dict[str, float]]) -> float:
    """Compute aggregate data drift score across all monitored features."""

    if not feature_drift:
        return 0.0
    scores = [float(stats["drift_score"]) for stats in feature_drift.values()]
    return sum(scores) / len(scores)
