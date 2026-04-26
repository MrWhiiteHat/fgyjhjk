"""Benchmark edge model runtimes for latency and basic output consistency."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from edge.on_device.runtimes.onnx_runtime_mobile import ONNXRuntimeMobileWrapper
from edge.on_device.runtimes.tflite_runtime import TFLiteRuntimeWrapper


def benchmark_runtime(runtime, image_path: str, runs: int = 20, warmup: int = 3) -> dict[str, Any]:
    """Benchmark a loaded runtime with repeated inference runs."""
    runtime.load_model()
    try:
        for _ in range(max(0, int(warmup))):
            _ = runtime.predict(image_path)

        latencies = []
        payload = None
        for _ in range(max(1, int(runs))):
            start = time.perf_counter()
            payload = runtime.predict(image_path)
            latencies.append((time.perf_counter() - start) * 1000.0)

        return {
            "runtime": runtime.get_metadata().runtime_name,
            "model_path": runtime.get_metadata().model_path,
            "runs": int(runs),
            "warmup": int(warmup),
            "latency_ms_mean": round(float(np.mean(latencies)), 4),
            "latency_ms_p95": round(float(np.percentile(latencies, 95)), 4),
            "latency_ms_p99": round(float(np.percentile(latencies, 99)), 4),
            "sample_prediction": payload,
        }
    finally:
        runtime.unload_model()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark edge model runtimes")
    parser.add_argument("--image", required=True, type=str)
    parser.add_argument("--onnx", default="", type=str)
    parser.add_argument("--tflite", default="", type=str)
    parser.add_argument("--runs", default=20, type=int)
    parser.add_argument("--warmup", default=3, type=int)
    parser.add_argument("--output", default="edge/on_device/model_conversion/benchmark_report.json", type=str)
    args = parser.parse_args()

    image_path = str(Path(args.image))
    results: list[dict[str, Any]] = []

    if args.onnx:
        onnx_runtime = ONNXRuntimeMobileWrapper(model_path=args.onnx)
        results.append(benchmark_runtime(onnx_runtime, image_path=image_path, runs=args.runs, warmup=args.warmup))

    if args.tflite:
        tflite_runtime = TFLiteRuntimeWrapper(model_path=args.tflite)
        results.append(benchmark_runtime(tflite_runtime, image_path=image_path, runs=args.runs, warmup=args.warmup))

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image": image_path,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
