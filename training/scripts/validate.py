"""Standalone validation script for evaluating a checkpoint on validation split."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from torch.utils.data import DataLoader

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.data.dataset import build_datasets, collate_batch
from training.data.transforms import build_transforms
from training.engine.evaluator import evaluate_model
from training.engine.losses import build_loss
from training.models.model_factory import create_model
from training.utils.checkpoint import load_model_for_inference
from training.utils.device import resolve_device, should_use_amp
from training.utils.helpers import load_yaml
from training.utils.logger import get_experiment_logger


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for validation run."""
    parser = argparse.ArgumentParser(description="Validate best model on validation split")
    parser.add_argument("--config", type=str, default="training/configs/train_config.yaml", help="Config path")
    parser.add_argument("--checkpoint", type=str, default="", help="Checkpoint path (defaults to best_model.pt)")
    return parser.parse_args()


def main() -> None:
    """Load checkpoint and evaluate on validation split."""
    args = parse_args()
    config = load_yaml(args.config)

    config["log_dir"] = str((Path(config["log_dir"]) / config["experiment_name"]).as_posix())
    config["predictions_dir"] = str((Path(config["predictions_dir"]) / config["experiment_name"]).as_posix())
    config["checkpoint_dir"] = str((Path(config["checkpoint_dir"]) / config["experiment_name"]).as_posix())

    logger, _ = get_experiment_logger(config["experiment_name"], Path(config["log_dir"]))

    device = resolve_device(config.get("device", "auto"), logger)
    use_amp = should_use_amp(config.get("use_amp", False), device, logger)

    datasets = build_datasets(config=config, transforms_map=build_transforms(config), logger=logger)
    num_workers = int(config.get("num_workers", 0))
    pin_memory = bool(config.get("pin_memory", False))
    if device.type == "cpu" and num_workers > 0:
        logger.warning(
            "CPU execution detected. For stability, forcing num_workers=0 for validation dataloader."
        )
        num_workers = 0
    if device.type != "cuda":
        pin_memory = False

    val_loader = DataLoader(
        datasets["val"],
        batch_size=int(config["batch_size"]),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=bool(config.get("persistent_workers", False) and num_workers > 0),
        collate_fn=collate_batch,
    )

    model = create_model(config, logger).to(device)
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else Path(config["checkpoint_dir"]) / "best_model.pt"
    load_model_for_inference(model, checkpoint_path=checkpoint_path, map_location=device, strict=True, logger=logger)

    criterion = build_loss(config, logger)

    val_pred_path = Path(config["predictions_dir"]) / "validation_predictions.csv"
    metrics, _ = evaluate_model(
        model=model,
        dataloader=val_loader,
        criterion=criterion,
        device=device,
        threshold=float(config.get("threshold", 0.5)),
        use_amp=use_amp,
        split="val",
        predictions_path=val_pred_path,
        logger=logger,
    )

    print("Validation Metrics")
    print(f"Loss: {float(metrics['loss']):.6f}")
    print(f"Accuracy: {float(metrics['accuracy']):.6f}")
    print(f"Precision: {float(metrics['precision']):.6f}")
    print(f"Recall: {float(metrics['recall']):.6f}")
    print(f"F1: {float(metrics['f1']):.6f}")
    print(f"ROC-AUC: {float(metrics['roc_auc']):.6f}")
    print(f"PR-AUC: {float(metrics['pr_auc']):.6f}")


if __name__ == "__main__":
    main()
