"""Shadow deployment evaluator for candidate model observability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShadowComparison:
    """Shadow deployment comparison output."""

    total_requests: int
    prediction_disagreement_rate: float
    candidate_accuracy: float | None
    production_accuracy: float | None
    candidate_latency_ms: float
    production_latency_ms: float


class ShadowDeploy:
    """Runs candidate model in shadow mode without serving user-facing output."""

    def evaluate(self, *, production_model, candidate_model, requests: list[dict]) -> ShadowComparison:
        """Compute shadow metrics between candidate and production models."""

        if not requests:
            return ShadowComparison(0, 0.0, None, None, 0.0, 0.0)

        disagreements = 0
        labeled = 0
        prod_correct = 0
        cand_correct = 0

        prod_latency = []
        cand_latency = []

        for request in requests:
            features = dict(request.get("features") or {})
            prod_pred = int(production_model.predict(features))
            cand_pred = int(candidate_model.predict(features))
            if prod_pred != cand_pred:
                disagreements += 1

            prod_latency.append(float(request.get("production_latency_ms", 0.0)))
            cand_latency.append(float(request.get("candidate_latency_ms", 0.0)))

            if request.get("label") is not None:
                labeled += 1
                label = int(request["label"])
                if prod_pred == label:
                    prod_correct += 1
                if cand_pred == label:
                    cand_correct += 1

        total = len(requests)
        return ShadowComparison(
            total_requests=total,
            prediction_disagreement_rate=disagreements / total,
            candidate_accuracy=(cand_correct / labeled) if labeled else None,
            production_accuracy=(prod_correct / labeled) if labeled else None,
            candidate_latency_ms=(sum(cand_latency) / len(cand_latency)) if cand_latency else 0.0,
            production_latency_ms=(sum(prod_latency) / len(prod_latency)) if prod_latency else 0.0,
        )
