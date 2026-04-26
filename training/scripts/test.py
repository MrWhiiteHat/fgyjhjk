"""Final test-only evaluation script for locked checkpoint assessment."""

from __future__ import annotations

import argparse
import json
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
from training.utils.visualization import generate_experiment_report, plot_confusion_matrix


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for test evaluation."""
    parser = argparse.ArgumentParser(description="Run final test evaluation from best checkpoint")
    parser.add_argument("--config", type=str, default="training/configs/train_config.yaml", help="Config path")
    parser.add_argument("--checkpoint", type=str, default="", help="Checkpoint path (defaults to best_model.pt)")
    return parser.parse_args()


def main() -> None:
    """Evaluate best model on test split one time after training finalization."""
    args = parse_args()
    config = load_yaml(args.config)

    config["log_dir"] = str((Path(config["log_dir"]) / config["experiment_name"]).as_posix())
    config["predictions_dir"] = str((Path(config["predictions_dir"]) / config["experiment_name"]).as_posix())
    config["checkpoint_dir"] = str((Path(config["checkpoint_dir"]) / config["experiment_name"]).as_posix())
    config["report_dir"] = str((Path(config["report_dir"]) / config["experiment_name"]).as_posix())
    config["plots_dir"] = str((Path(config["plots_dir"]) / config["experiment_name"]).as_posix())

    logger, _ = get_experiment_logger(config["experiment_name"], Path(config["log_dir"]))

    device = resolve_device(config.get("device", "auto"), logger)
    use_amp = should_use_amp(config.get("use_amp", False), device, logger)

    datasets = build_datasets(config=config, transforms_map=build_transforms(config), logger=logger)
    num_workers = int(config.get("num_workers", 0))
    pin_memory = bool(config.get("pin_memory", False))
    if device.type == "cpu" and num_workers > 0:
        logger.warning(
            "CPU execution detected. For stability, forcing num_workers=0 for test dataloader."
        )
        num_workers = 0
    if device.type != "cuda":
        pin_memory = False

    test_loader = DataLoader(
        datasets["test"],
        batch_size=int(config["batch_size"]),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=bool(config.get("persistent_workers", False) and num_workers > 0),
        collate_fn=collate_batch,
    )

    checkpoint_path = Path(args.checkpoint) if args.checkpoint else Path(config["checkpoint_dir"]) / "best_model.pt"

    model = create_model(config=config, logger=logger).to(device)
    load_model_for_inference(model=model, checkpoint_path=checkpoint_path, map_location=device, strict=True, logger=logger)

    criterion = build_loss(config, logger)

    test_predictions_path = Path(config["predictions_dir"]) / "test_predictions.csv"
    metrics, _ = evaluate_model(
        model=model,
        dataloader=test_loader,
        criterion=criterion,
        device=device,
        threshold=float(config.get("threshold", 0.5)),
        use_amp=use_amp,
        split="test",
        predictions_path=test_predictions_path,
        logger=logger,
    )

    confusion_path = Path(config["plots_dir"]) / "test_confusion_matrix.png"
    plot_confusion_matrix(metrics["confusion_matrix"], confusion_path, "Test Confusion Matrix")

    summary_payload = {
        "experiment_name": config["experiment_name"],
        "checkpoint": str(checkpoint_path.as_posix()),
        "threshold": float(config.get("threshold", 0.5)),
        "metrics": {
            "loss": float(metrics["loss"]),
            "accuracy": float(metrics["accuracy"]),
            "precision": float(metrics["precision"]),
            "recall": float(metrics["recall"]),
            "f1": float(metrics["f1"]),
            "roc_auc": float(metrics["roc_auc"]),
            "pr_auc": float(metrics["pr_auc"]),
            "balanced_accuracy": float(metrics["balanced_accuracy"]),
        },
        "prediction_csv": str(test_predictions_path.as_posix()),
        "confusion_matrix_plot": str(confusion_path.as_posix()),
    }

    report_path = Path(config["report_dir"]) / "test_summary.json"
    generate_experiment_report(report_path, summary_payload)

    txt_report = Path(config["report_dir"]) / "test_summary_short.txt"
    with txt_report.open("w", encoding="utf-8") as handle:
        handle.write("Test Summary\n")
        handle.write("============\n")
        for key, value in summary_payload["metrics"].items():
            handle.write(f"{key}: {value}\n")

    with (Path(config["report_dir"]) / "test_summary_metrics_only.json").open("w", encoding="utf-8") as handle:
        json.dump(summary_payload["metrics"], handle, indent=2)

    print("Test evaluation completed")
    print(f"Checkpoint: {checkpoint_path.as_posix()}")
    print(f"Predictions: {test_predictions_path.as_posix()}")
    print(f"Report: {report_path.as_posix()}")


if __name__ == "__main__":
    main()
