"""Bias checks for subgroup error-rate disparity changes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BiasCheckResult:
    """Bias evaluation result for candidate versus production."""

    passed: bool
    production_disparity: float
    candidate_disparity: float
    disparity_increase: float


class BiasChecks:
    """Evaluates subgroup fairness shifts before rollout."""

    def evaluate(
        self,
        *,
        candidate_model,
        production_model,
        samples: list[dict],
        group_key: str = "group",
        max_disparity_increase: float = 0.03,
    ) -> BiasCheckResult:
        """Measure disparity increase between candidate and production models."""

        prod = self._group_error_rates(production_model, samples, group_key)
        cand = self._group_error_rates(candidate_model, samples, group_key)

        prod_disp = self._disparity(prod)
        cand_disp = self._disparity(cand)
        increase = cand_disp - prod_disp
        passed = increase <= float(max_disparity_increase)

        return BiasCheckResult(
            passed=passed,
            production_disparity=prod_disp,
            candidate_disparity=cand_disp,
            disparity_increase=increase,
        )

    @staticmethod
    def _group_error_rates(model, samples: list[dict], group_key: str) -> dict[str, float]:
        grouped: dict[str, list[int]] = {}

        for sample in samples:
            if sample.get("label") is None:
                continue
            group = str(sample.get(group_key, "unknown"))
            prediction = int(model.predict(dict(sample.get("features") or {})))
            label = int(sample["label"])
            error = 1 if prediction != label else 0
            grouped.setdefault(group, []).append(error)

        rates: dict[str, float] = {}
        for group, errors in grouped.items():
            rates[group] = sum(errors) / len(errors) if errors else 0.0
        return rates

    @staticmethod
    def _disparity(group_rates: dict[str, float]) -> float:
        if not group_rates:
            return 0.0
        values = list(group_rates.values())
        return max(values) - min(values)
