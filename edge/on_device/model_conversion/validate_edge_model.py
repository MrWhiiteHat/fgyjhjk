"""Validate edge artifact predictions against reference backend/evaluation outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from edge.on_device.runtimes.onnx_runtime_mobile import ONNXRuntimeMobileWrapper
from edge.on_device.runtimes.tflite_runtime import TFLiteRuntimeWrapper


def _load_reference_predictions(path: Path) -> dict[str, float]:
    """Load reference probabilities keyed by image path from CSV/JSON."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Reference predictions not found: {path}")

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return {str(item["image_path"]): float(item["fake_probability"]) for item in payload if isinstance(item, dict) and "image_path" in item}
        if isinstance(payload, dict):
            return {str(k): float(v) for k, v in payload.items()}
        raise ValueError("Unsupported JSON prediction format")

    if path.suffix.lower() == ".csv":
        result = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                image_path = str(row.get("image_path", "")).strip()
                if not image_path:
                    continue
                fake_prob = row.get("fake_probability")
                if fake_prob is None:
                    fake_prob = row.get("predicted_probability")
                result[image_path] = float(fake_prob)
        return result

    raise ValueError("Reference file must be .csv or .json")


def _runtime_from_args(runtime_kind: str, model_path: str):
    if runtime_kind == "onnx":
        return ONNXRuntimeMobileWrapper(model_path=model_path)
    if runtime_kind == "tflite":
        return TFLiteRuntimeWrapper(model_path=model_path)
    raise ValueError(f"Unsupported runtime kind: {runtime_kind}")


def validate_model(
    runtime_kind: str,
    model_path: str,
    reference_file: str,
    max_samples: int = 100,
    abs_prob_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Run edge inference and compare probabilities against reference outputs."""
    reference = _load_reference_predictions(Path(reference_file))
    items = list(reference.items())[: max(1, int(max_samples))]

    runtime = _runtime_from_args(runtime_kind=runtime_kind, model_path=model_path)
    runtime.load_model()

    deviations: list[float] = []
    failures: list[dict[str, Any]] = []
    try:
        for image_path, expected_fake_prob in items:
            try:
                payload = runtime.predict(image_path)
                observed_fake_prob = float(payload["probabilities"]["FAKE"])
                delta = abs(observed_fake_prob - float(expected_fake_prob))
                deviations.append(delta)
                if delta > float(abs_prob_tolerance):
                    failures.append(
                        {
                            "image_path": image_path,
                            "expected_fake_probability": float(expected_fake_prob),
                            "observed_fake_probability": observed_fake_prob,
                            "abs_delta": round(delta, 6),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "image_path": image_path,
                        "error": str(exc),
                    }
                )
    finally:
        runtime.unload_model()

    avg_delta = float(np.mean(deviations)) if deviations else None
    p95_delta = float(np.percentile(deviations, 95)) if deviations else None

    return {
        "runtime": runtime_kind,
        "model_path": str(Path(model_path).as_posix()),
        "checked_samples": len(items),
        "successful_samples": len(deviations),
        "abs_probability_tolerance": float(abs_prob_tolerance),
        "average_abs_deviation": round(avg_delta, 6) if avg_delta is not None else None,
        "p95_abs_deviation": round(p95_delta, 6) if p95_delta is not None else None,
        "pass": len(failures) == 0,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate converted edge model")
    parser.add_argument("--runtime", required=True, choices=["onnx", "tflite"])
    parser.add_argument("--model", required=True, type=str)
    parser.add_argument("--reference", required=True, type=str)
    parser.add_argument("--max-samples", default=100, type=int)
    parser.add_argument("--abs-prob-tolerance", default=0.05, type=float)
    parser.add_argument("--output", default="edge/on_device/model_conversion/validation_report.json", type=str)
    args = parser.parse_args()

    report = validate_model(
        runtime_kind=args.runtime,
        model_path=args.model,
        reference_file=args.reference,
        max_samples=args.max_samples,
        abs_prob_tolerance=args.abs_prob_tolerance,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("pass", False) else 2


if __name__ == "__main__":
    raise SystemExit(main())
