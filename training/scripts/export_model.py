"""Export trained model to PyTorch, TorchScript, and ONNX formats."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.models.model_factory import create_model
from training.utils.checkpoint import load_checkpoint, load_model_for_inference
from training.utils.helpers import load_yaml
from training.utils.logger import get_experiment_logger


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for export script."""
    parser = argparse.ArgumentParser(description="Export trained model artifacts")
    parser.add_argument("--config", type=str, default="training/configs/train_config.yaml", help="Config path")
    parser.add_argument("--checkpoint", type=str, default="", help="Checkpoint path (defaults to best_model.pt)")
    parser.add_argument("--export-dir", type=str, default="", help="Optional override export directory")
    return parser.parse_args()


def main() -> None:
    """Export best model to .pth, TorchScript, and ONNX formats."""
    args = parse_args()
    config = load_yaml(args.config)

    config["log_dir"] = str((Path(config["log_dir"]) / config["experiment_name"]).as_posix())
    config["checkpoint_dir"] = str((Path(config["checkpoint_dir"]) / config["experiment_name"]).as_posix())

    logger, _ = get_experiment_logger(config["experiment_name"], Path(config["log_dir"]))

    checkpoint_path = Path(args.checkpoint) if args.checkpoint else Path(config["checkpoint_dir"]) / "best_model.pt"
    export_dir = Path(args.export_dir) if args.export_dir else Path(config["checkpoint_dir"]) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    model = create_model(config=config, logger=logger)
    load_model_for_inference(model=model, checkpoint_path=checkpoint_path, map_location="cpu", strict=True, logger=logger)
    model.eval()

    checkpoint_payload = load_checkpoint(checkpoint_path, map_location="cpu", logger=logger)
    state_dict = checkpoint_payload.get("model_state_dict", checkpoint_payload)

    pth_path = export_dir / "model_state_dict.pth"
    torch.save(state_dict, pth_path)

    image_size = int(config["image_size"])
    dummy_input = torch.randn(1, 3, image_size, image_size)

    ts_path = export_dir / "model_torchscript.pt"
    traced = torch.jit.trace(model, dummy_input)
    traced.save(str(ts_path))

    onnx_path = export_dir / "model.onnx"
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["logit"],
        dynamic_axes={"input": {0: "batch"}, "logit": {0: "batch"}},
    )

    if not pth_path.exists() or not ts_path.exists() or not onnx_path.exists():
        raise RuntimeError("Model export failed: one or more export files are missing")

    inference_doc = export_dir / "inference_input_format.txt"
    with inference_doc.open("w", encoding="utf-8") as handle:
        handle.write("Input Tensor Format\n")
        handle.write("===================\n")
        handle.write("Shape: [batch_size, 3, image_size, image_size]\n")
        handle.write("Dtype: float32\n")
        handle.write("Channel order: RGB\n")
        handle.write("Normalization: configured mean/std in training/configs/train_config.yaml\n")

    print("Model export completed")
    print(f"Checkpoint: {checkpoint_path.as_posix()}")
    print(f"PyTorch: {pth_path.as_posix()}")
    print(f"TorchScript: {ts_path.as_posix()}")
    print(f"ONNX: {onnx_path.as_posix()}")


if __name__ == "__main__":
    main()
