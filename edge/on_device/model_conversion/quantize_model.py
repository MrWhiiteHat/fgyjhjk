"""Quantization helpers for ONNX and TFLite edge models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def quantize_onnx_dynamic(onnx_path: str, output_path: str) -> dict[str, Any]:
    """Apply dynamic INT8 quantization for ONNX model where supported."""
    src = Path(onnx_path)
    dst = Path(output_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"ONNX not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        model_input=str(src),
        model_output=str(dst),
        weight_type=QuantType.QInt8,
    )

    return {
        "format": "onnx",
        "quantization": "dynamic_int8",
        "source": str(src.as_posix()),
        "output": str(dst.as_posix()),
    }


def quantize_tflite_post_training(
    saved_model_dir: str,
    output_tflite: str,
    fp16: bool = True,
) -> dict[str, Any]:
    """Post-training quantization for TensorFlow SavedModel to TFLite."""
    import tensorflow as tf

    src = Path(saved_model_dir)
    dst = Path(output_tflite)
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"SavedModel directory not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    converter = tf.lite.TFLiteConverter.from_saved_model(str(src))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    if fp16:
        converter.target_spec.supported_types = [tf.float16]
    quantized = converter.convert()
    dst.write_bytes(quantized)

    return {
        "format": "tflite",
        "quantization": "post_training_fp16" if fp16 else "post_training_default",
        "source": str(src.as_posix()),
        "output": str(dst.as_posix()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Quantize edge model artifacts")
    parser.add_argument("--mode", required=True, choices=["onnx_dynamic", "tflite_post"])
    parser.add_argument("--input", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--fp32", action="store_true")
    args = parser.parse_args()

    if args.mode == "onnx_dynamic":
        result = quantize_onnx_dynamic(args.input, args.output)
    else:
        result = quantize_tflite_post_training(args.input, args.output, fp16=not bool(args.fp32))

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
