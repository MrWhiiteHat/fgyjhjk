"""Export ONNX model to CoreML package if coremltools is available."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def export_coreml_from_onnx(
    onnx_path: str,
    output_mlpackage_path: str,
    fp16: bool = True,
) -> dict[str, Any]:
    """Convert ONNX to CoreML package using coremltools.

    This path is optional and requires coremltools with ONNX conversion support.
    """
    src = Path(onnx_path)
    dst = Path(output_mlpackage_path)

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"ONNX model not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        import coremltools as ct
    except Exception as exc:
        raise RuntimeError("coremltools is not installed") from exc

    compute_precision = ct.precision.FLOAT16 if fp16 else ct.precision.FLOAT32
    mlmodel = ct.converters.onnx.convert(model=str(src), minimum_deployment_target=ct.target.iOS15, compute_precision=compute_precision)
    mlmodel.save(str(dst))

    return {
        "format": "coreml",
        "source": str(src.as_posix()),
        "output_path": str(dst.as_posix()),
        "fp16": bool(fp16),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CoreML model from ONNX artifact")
    parser.add_argument("--onnx", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--fp32", action="store_true")
    args = parser.parse_args()

    result = export_coreml_from_onnx(
        onnx_path=args.onnx,
        output_mlpackage_path=args.output,
        fp16=not bool(args.fp32),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
