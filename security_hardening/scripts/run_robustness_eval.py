#!/usr/bin/env python
"""Run robustness evaluation using the perturbation benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security_hardening.evaluation.robustness_benchmark import RobustnessBenchmark


class HeuristicModel:
    """Minimal model adapter for benchmark execution."""

    def predict(self, features: dict[str, float]) -> int:
        score = 0.7 * float(features.get("x", 0.0)) + 0.3 * float(features.get("y", 0.0))
        return int(score >= 0.5)


def _load_samples(path: Path | None, sample_count: int) -> list[dict]:
    if path is None:
        rng = np.random.default_rng(9)
        samples: list[dict] = []
        for _ in range(sample_count):
            image = np.clip(rng.normal(120, 30, size=(96, 96, 3)), 0, 255).astype(np.uint8)
            label = int(float(np.mean(image)) > 120.0)
            samples.append({"image": image.tolist(), "label": label})
        return samples

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("samples json must be a list")
    normalized = []
    for item in payload:
        normalized.append({"image": item["image"], "label": int(item["label"])})
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Run robustness benchmark for security hardening")
    parser.add_argument("--samples", type=Path, default=None, help="Path to JSON list of samples with image+label")
    parser.add_argument("--sample-count", type=int, default=24, help="Generated sample count when --samples omitted")
    parser.add_argument("--max-degradation", type=float, default=0.12)
    parser.add_argument("--min-perturbed-accuracy", type=float, default=0.75)
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    args = parser.parse_args()

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "samples": str(args.samples) if args.samples else None,
                    "sample_count": args.sample_count,
                    "max_degradation": args.max_degradation,
                    "min_perturbed_accuracy": args.min_perturbed_accuracy,
                },
                indent=2,
            )
        )
        return 0

    samples = _load_samples(args.samples, args.sample_count)
    normalized = [{"image": np.asarray(s["image"], dtype=np.uint8), "label": int(s["label"])} for s in samples]

    benchmark = RobustnessBenchmark()
    result = benchmark.run(
        model=HeuristicModel(),
        samples=normalized,
        max_allowed_degradation=args.max_degradation,
        min_perturbed_accuracy=args.min_perturbed_accuracy,
    )

    print(
        json.dumps(
            {
                "passed": result.passed,
                "baseline_accuracy": result.baseline_accuracy,
                "perturbed_accuracy": result.perturbed_accuracy,
                "degradation": result.degradation,
                "per_case_accuracy": result.per_case_accuracy,
                "reasons": result.reasons,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
