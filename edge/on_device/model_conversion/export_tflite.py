"""Export ONNX model to TensorFlow Lite format where conversion toolchain is available."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def export_tflite_from_onnx(
    onnx_path: str,
    output_tflite_path: str,
    temp_saved_model_dir: str,
) -> dict[str, Any]:
    """Convert ONNX -> TensorFlow SavedModel -> TFLite using available CLI tools.

    Requires optional tools:
    - onnx2tf
    - tensorflow
    """
    src = Path(onnx_path)
    dst = Path(output_tflite_path)
    saved_model_dir = Path(temp_saved_model_dir)

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"ONNX model not found: {src}")

    saved_model_dir.mkdir(parents=True, exist_ok=True)
    dst.parent.mkdir(parents=True, exist_ok=True)

    onnx2tf_cmd = [
        "python",
        "-m",
        "onnx2tf",
        "-i",
        str(src),
        "-o",
        str(saved_model_dir),
    ]
    proc = subprocess.run(onnx2tf_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"onnx2tf conversion failed: {proc.stderr.strip() or proc.stdout.strip()}")

    import tensorflow as tf

    converter = tf.lite.TFLiteConverter.from_saved_model(str(saved_model_dir))
    tflite_model = converter.convert()
    dst.write_bytes(tflite_model)

    return {
        "format": "tflite",
        "source": str(src.as_posix()),
        "output_path": str(dst.as_posix()),
        "saved_model_dir": str(saved_model_dir.as_posix()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export TFLite model from ONNX artifact")
    parser.add_argument("--onnx", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--temp-saved-model", default="edge/on_device/model_conversion/tmp_saved_model", type=str)
    args = parser.parse_args()

    result = export_tflite_from_onnx(
        onnx_path=args.onnx,
        output_tflite_path=args.output,
        temp_saved_model_dir=args.temp_saved_model,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
