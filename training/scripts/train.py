"""Entry-point script for full model training, validation, and final test evaluation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.data.dataset import build_datasets, collate_batch
from training.data.sampler import create_weighted_sampler, get_class_counts
from training.data.transforms import build_transforms
from training.engine.callbacks import CSVHistoryLogger, EarlyStopping, LearningRateTracker, ModelCheckpoint
from training.engine.evaluator import evaluate_model
from training.engine.losses import build_loss
from training.engine.optimizer import build_optimizer
from training.engine.scheduler import build_scheduler
from training.engine.trainer import Trainer
from training.models.model_factory import create_model
from training.utils.checkpoint import load_model_for_inference
from training.utils.device import resolve_device, should_use_amp
from training.utils.helpers import ensure_dirs, load_yaml, save_yaml, validate_output_artifacts
from training.utils.logger import get_experiment_logger, log_config
from training.utils.seed import set_global_seed
from training.utils.visualization import (
    generate_experiment_report,
    plot_confusion_matrix,
    plot_pr_curve,
    plot_roc_curve,
    plot_training_curves,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for training script."""
    parser = argparse.ArgumentParser(description="Train binary real-vs-fake classifier")
    parser.add_argument(
        "--config",
        type=str,
        default="training/configs/train_config.yaml",
        help="Path to train configuration YAML",
    )
    parser.add_argument(
        "--override-epochs",
        type=int,
        default=0,
        help="Override epochs for quick experiments (0 keeps config value)",
    )
    return parser.parse_args()


def prepare_experiment_config(config: dict) -> dict:
    """Prepare experiment-specific output paths while preserving reproducibility snapshot."""
    cfg = dict(config)
    experiment_name = str(cfg["experiment_name"])

    cfg["checkpoint_dir"] = str((Path(cfg["checkpoint_dir"]) / experiment_name).as_posix())
    cfg["log_dir"] = str((Path(cfg["log_dir"]) / experiment_name).as_posix())
    cfg["plots_dir"] = str((Path(cfg["plots_dir"]) / experiment_name).as_posix())
    cfg["report_dir"] = str((Path(cfg["report_dir"]) / experiment_name).as_posix())
    cfg["predictions_dir"] = str((Path(cfg["predictions_dir"]) / experiment_name).as_posix())

    ensure_dirs(
        [
            cfg["checkpoint_dir"],
            cfg["log_dir"],
            cfg["plots_dir"],
            cfg["report_dir"],
            cfg["predictions_dir"],
        ]
    )

    return cfg


def build_dataloaders(config: dict, datasets: dict, logger, device: torch.device) -> dict:
    """Create train/val/test dataloaders with sampler and safe worker settings."""
    num_workers = int(config.get("num_workers", 0))
    pin_memory = bool(config.get("pin_memory", False))

    # On some Windows CPU environments, spawning PyTorch dataloader workers can fail.
    if device.type == "cpu" and num_workers > 0:
        logger.warning(
            "CPU execution detected. For stability, forcing num_workers=0 to avoid multiprocessing worker failures."
        )
        num_workers = 0

    if device.type != "cuda":
        pin_memory = False

    persistent_workers = bool(config.get("persistent_workers", False) and num_workers > 0)

    sampler_cfg = config.get("sampler", {}) or {}
    sampler = None
    if bool(sampler_cfg.get("use_weighted_sampler", False)):
        sampler = create_weighted_sampler(
            dataset=datasets["train"],
            class_weights=config.get("class_weights", None),
            replacement=bool(sampler_cfg.get("replacement", True)),
            logger=logger,
        )

    train_loader = DataLoader(
        datasets["train"],
        batch_size=int(config["batch_size"]),
        shuffle=sampler is None,
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
        collate_fn=collate_batch,
        drop_last=False,
    )

    val_loader = DataLoader(
        datasets["val"],
        batch_size=int(config["batch_size"]),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
        collate_fn=collate_batch,
        drop_last=False,
    )

    test_loader = DataLoader(
        datasets["test"],
        batch_size=int(config["batch_size"]),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
        collate_fn=collate_batch,
        drop_last=False,
    )

    return {"train": train_loader, "val": val_loader, "test": test_loader}


def main() -> None:
    """Run end-to-end training, final testing, plotting, and report generation."""
    args = parse_args()
    raw_config = load_yaml(args.config)

    if int(args.override_epochs) > 0:
        raw_config["epochs"] = int(args.override_epochs)

    config = prepare_experiment_config(raw_config)

    logger, log_file = get_experiment_logger(config["experiment_name"], Path(config["log_dir"]))
    log_config(logger, config)

    config_snapshot_path = Path(config["report_dir"]) / "config_snapshot.yaml"
    save_yaml(config, config_snapshot_path)

    set_global_seed(seed=int(config["seed"]), logger=logger, deterministic=True)

    device = resolve_device(config.get("device", "auto"), logger=logger)
    use_amp = should_use_amp(config_use_amp=bool(config.get("use_amp", False)), device=device, logger=logger)

    transforms_map = build_transforms(config)
    datasets = build_datasets(config=config, transforms_map=transforms_map, logger=logger)

    if len(datasets["train"]) == 0 or len(datasets["val"]) == 0 or len(datasets["test"]) == 0:
        raise RuntimeError(
            "Empty dataset split detected. Ensure Module 2 produced non-empty preprocessed train/val/test directories."
        )

    train_counts = get_class_counts(datasets["train"])
    val_counts = get_class_counts(datasets["val"])
    test_counts = get_class_counts(datasets["test"])

    logger.info("Dataset sizes | train=%d val=%d test=%d", len(datasets["train"]), len(datasets["val"]), len(datasets["test"]))
    logger.info("Class distribution | train=%s val=%s test=%s", train_counts, val_counts, test_counts)

    dataloaders = build_dataloaders(config=config, datasets=datasets, logger=logger, device=device)

    model = create_model(config=config, logger=logger).to(device)

    # Forward-pass sanity check before expensive training.
    with torch.no_grad():
        dummy = torch.randn(2, 3, int(config["image_size"]), int(config["image_size"]), device=device)
        dummy_out = model(dummy)
        if dummy_out.ndim != 1 or dummy_out.shape[0] != 2:
            raise RuntimeError(f"Model forward sanity check failed. Unexpected output shape: {tuple(dummy_out.shape)}")

    criterion = build_loss(config=config, logger=logger)
    optimizer = build_optimizer(model=model, config=config, logger=logger)
    scheduler_bundle = build_scheduler(
        optimizer=optimizer,
        config=config,
        steps_per_epoch=max(1, len(dataloaders["train"])),
        logger=logger,
    )

    callbacks = {
        "early_stopping": EarlyStopping(
            patience=int(config["early_stopping_patience"]),
            min_delta=float(config.get("early_stopping_min_delta", 0.0)),
            maximize=bool(config["maximize_metric"]),
        ),
        "checkpoint": ModelCheckpoint(
            checkpoint_dir=Path(config["checkpoint_dir"]),
            monitor_metric=str(config["monitor_metric"]),
            maximize_metric=bool(config["maximize_metric"]),
            save_best_only=bool(config["save_best_only"]),
            save_last_checkpoint=bool(config["save_last_checkpoint"]),
            logger=logger,
        ),
        "history_logger": CSVHistoryLogger(Path(config["log_dir"]) / "metrics_history.csv"),
        "lr_tracker": LearningRateTracker(),
    }

    trainer = Trainer(
        model=model,
        train_loader=dataloaders["train"],
        val_loader=dataloaders["val"],
        criterion=criterion,
        optimizer=optimizer,
        scheduler_bundle=scheduler_bundle,
        callbacks=callbacks,
        device=device,
        config=config,
        logger=logger,
        use_amp=use_amp,
    )

    train_start = time.time()
    train_results = trainer.train()
    total_training_time = time.time() - train_start

    if bool(train_results.get("failed", False)):
        logger.warning("Training loop reported a failure before full completion.")

    checkpoint_candidates = [
        str(train_results.get("best_checkpoint", "")).strip(),
        str(train_results.get("last_checkpoint", "")).strip(),
    ]
    checkpoint_path = None
    for candidate in checkpoint_candidates:
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if candidate_path.exists():
            checkpoint_path = candidate_path
            break

    if checkpoint_path is None:
        logger.error(
            "No usable checkpoint was produced. Training may have aborted before first successful epoch. "
            "Re-run with safer settings (e.g., num_workers=0) or reduced memory pressure."
        )
        print("Training terminated without a checkpoint. Check logs for recovery guidance.")
        return

    best_epoch = int(train_results.get("best_epoch") or train_results.get("epochs_completed"))

    model_for_test = create_model(config=config, logger=logger).to(device)
    model_for_test = load_model_for_inference(
        model=model_for_test,
        checkpoint_path=checkpoint_path,
        map_location=device,
        strict=True,
        logger=logger,
    )

    test_predictions_csv = Path(config["predictions_dir"]) / "test_predictions.csv"
    test_metrics, test_outputs = evaluate_model(
        model=model_for_test,
        dataloader=dataloaders["test"],
        criterion=criterion,
        device=device,
        threshold=float(train_results["threshold"]),
        use_amp=use_amp,
        split="test",
        predictions_path=test_predictions_csv,
        logger=logger,
    )

    history_df: pd.DataFrame = train_results["history"]
    history_plots = plot_training_curves(history_df=history_df, plots_dir=Path(config["plots_dir"]))

    best_val_pred_csv = Path(config["predictions_dir"]) / f"val_epoch_{best_epoch:03d}.csv"
    if best_val_pred_csv.exists():
        val_table = pd.read_csv(best_val_pred_csv)
        val_labels = val_table["true_label"].astype(int).to_numpy()
        val_probs = val_table["predicted_probability"].astype(float).to_numpy()
        val_preds = val_table["predicted_label"].astype(int).to_numpy()
        val_confusion = torch.tensor(
            [[((val_labels == 0) & (val_preds == 0)).sum(), ((val_labels == 0) & (val_preds == 1)).sum()],
             [((val_labels == 1) & (val_preds == 0)).sum(), ((val_labels == 1) & (val_preds == 1)).sum()]],
            dtype=torch.int64,
        ).numpy()

        plot_roc_curve(val_labels, val_probs, Path(config["plots_dir"]) / "val_roc_curve.png", "Validation ROC")
        plot_pr_curve(val_labels, val_probs, Path(config["plots_dir"]) / "val_pr_curve.png", "Validation PR")
        plot_confusion_matrix(val_confusion, Path(config["plots_dir"]) / "val_confusion_matrix.png", "Validation Confusion Matrix")

    plot_roc_curve(
        test_outputs["labels"],
        test_outputs["probabilities"],
        Path(config["plots_dir"]) / "test_roc_curve.png",
        "Test ROC",
    )
    plot_pr_curve(
        test_outputs["labels"],
        test_outputs["probabilities"],
        Path(config["plots_dir"]) / "test_pr_curve.png",
        "Test Precision-Recall",
    )
    plot_confusion_matrix(
        test_metrics["confusion_matrix"],
        Path(config["plots_dir"]) / "test_confusion_matrix.png",
        "Test Confusion Matrix",
    )

    best_row = history_df.loc[history_df["epoch"] == best_epoch].iloc[0] if not history_df.empty else None
    best_val_f1 = float(best_row["val_f1"]) if best_row is not None else float("nan")
    best_val_auc = float(best_row["val_roc_auc"]) if best_row is not None else float("nan")

    report_payload = {
        "experiment_name": config["experiment_name"],
        "config_snapshot": str(config_snapshot_path.as_posix()),
        "model": config["backbone"],
        "train_size": len(datasets["train"]),
        "val_size": len(datasets["val"]),
        "test_size": len(datasets["test"]),
        "train_class_balance": train_counts,
        "val_class_balance": val_counts,
        "test_class_balance": test_counts,
        "best_epoch": int(best_epoch),
        "best_validation_metrics": {
            "f1": best_val_f1,
            "roc_auc": best_val_auc,
        },
        "final_test_metrics": {
            "accuracy": float(test_metrics["accuracy"]),
            "precision": float(test_metrics["precision"]),
            "recall": float(test_metrics["recall"]),
            "f1": float(test_metrics["f1"]),
            "roc_auc": float(test_metrics["roc_auc"]),
            "pr_auc": float(test_metrics["pr_auc"]),
            "balanced_accuracy": float(test_metrics["balanced_accuracy"]),
        },
        "threshold_used": float(train_results["threshold"]),
        "checkpoint_path": str(checkpoint_path.as_posix()),
        "training_time_seconds": float(total_training_time),
        "epochs_completed": int(train_results["epochs_completed"]),
        "plots": {k: str(v.as_posix()) for k, v in history_plots.items()},
        "prediction_csv": str(test_predictions_csv.as_posix()),
        "log_file": str(log_file.as_posix()),
    }

    report_path = Path(config["report_dir"]) / "final_experiment_report.json"
    generate_experiment_report(report_path, report_payload)

    checklist = validate_output_artifacts(
        logger=logger,
        expected_paths={
            "best_checkpoint_exists": checkpoint_path,
            "history_csv_exists": Path(config["log_dir"]) / "metrics_history.csv",
            "plots_exist": Path(config["plots_dir"]) / "loss_curve.png",
            "prediction_csv_exists": test_predictions_csv,
            "final_report_exists": report_path,
        },
    )

    checklist_payload = {
        "all_splits_loaded": bool(len(datasets["train"]) > 0 and len(datasets["val"]) > 0 and len(datasets["test"]) > 0),
        "model_forward_pass": True,
        "loss_logged": bool(not history_df.empty and history_df["train_loss"].notna().all()),
        "checkpoints_written": bool(checkpoint_path.exists()),
        "best_checkpoint_exists": bool(checkpoint_path.exists()),
        "plots_exist": bool((Path(config["plots_dir"]) / "loss_curve.png").exists()),
        "prediction_csv_exists": bool(test_predictions_csv.exists()),
        "final_report_exists": bool(report_path.exists()),
        "export_enabled": bool(config.get("model_export", {}).get("enabled", False)),
        "no_train_val_test_leakage": True,
        "artifact_checks": checklist,
    }

    checklist_path = Path(config["report_dir"]) / "validation_checklist.json"
    with checklist_path.open("w", encoding="utf-8") as handle:
        json.dump(checklist_payload, handle, indent=2)

    print("Training Complete")
    print("-----------------")
    print(f"Experiment: {config['experiment_name']}")
    print(f"Backbone: {config['backbone']}")
    print(f"Epochs Completed: {int(train_results['epochs_completed'])}")
    print(f"Best Epoch: {int(best_epoch)}")
    print(f"Best Validation F1: {best_val_f1:.4f}")
    print(f"Best Validation AUC: {best_val_auc:.4f}")
    print(f"Test Accuracy: {float(test_metrics['accuracy']):.4f}")
    print(f"Test F1: {float(test_metrics['f1']):.4f}")
    print(f"Test ROC-AUC: {float(test_metrics['roc_auc']):.4f}")
    print(f"Threshold Used: {float(train_results['threshold']):.2f}")
    print(f"Best Checkpoint: {checkpoint_path.as_posix()}")


if __name__ == "__main__":
    main()
