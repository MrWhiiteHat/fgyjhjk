"""Export trained model checkpoint to ONNX format for edge/mobile runtimes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch


def export_onnx(
    checkpoint_path: str,
    output_path: str,
    input_size: tuple[int, int] = (224, 224),
    opset: int = 17,
    dynamic_batch: bool = True,
) -> dict[str, Any]:
    """Export PyTorch checkpoint/module to ONNX and emit metadata."""
    src = Path(checkpoint_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {src}")

    model = torch.load(str(src), map_location="cpu")
    if isinstance(model, dict) and "model_state_dict" in model:
        raise ValueError("State dict checkpoint requires architecture recreation; provide scripted/module checkpoint")

    if not isinstance(model, torch.nn.Module):
        raise TypeError("Loaded checkpoint is not a torch.nn.Module")

    model.eval()
    dummy = torch.randn(1, 3, int(input_size[1]), int(input_size[0]), dtype=torch.float32)

    dynamic_axes = {"input": {0: "batch"}, "output": {0: "batch"}} if dynamic_batch else None

    torch.onnx.export(
        model,
        dummy,
        str(dst),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
        opset_version=int(opset),
        do_constant_folding=True,
    )

    return {
        "format": "onnx",
        "output_path": str(dst.as_posix()),
        "opset": int(opset),
        "dynamic_batch": bool(dynamic_batch),
        "input_size": [int(input_size[0]), int(input_size[1])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export model checkpoint to ONNX edge artifact")
    parser.add_argument("--checkpoint", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--width", default=224, type=int)
    parser.add_argument("--height", default=224, type=int)
    parser.add_argument("--opset", default=17, type=int)
    parser.add_argument("--dynamic-batch", action="store_true")
    args = parser.parse_args()

    result = export_onnx(
        checkpoint_path=args.checkpoint,
        output_path=args.output,
        input_size=(args.width, args.height),
        opset=args.opset,
        dynamic_batch=args.dynamic_batch,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
