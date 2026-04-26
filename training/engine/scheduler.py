"""Learning-rate scheduler builders and stepping logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import torch


@dataclass
class SchedulerBundle:
    """Container for scheduler object and required stepping mode."""

    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler]
    step_mode: str


def build_scheduler(
    optimizer: torch.optim.Optimizer,
    config: Dict,
    steps_per_epoch: int,
    logger: logging.Logger,
) -> SchedulerBundle:
    """Create scheduler and define whether stepping is per-batch, per-epoch, or metric-driven."""
    scheduler_name = str(config.get("scheduler", "none")).strip().lower()
    params = config.get("scheduler_params", {}) or {}

    if scheduler_name in {"none", ""}:
        logger.info("Scheduler disabled")
        return SchedulerBundle(scheduler=None, step_mode="none")

    if scheduler_name == "steplr":
        step_size = int(params.get("step_size", 5))
        gamma = float(params.get("gamma", 0.1))
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)
        return SchedulerBundle(scheduler=scheduler, step_mode="epoch")

    if scheduler_name == "cosineannealinglr":
        t_max = int(params.get("T_max", max(1, int(config.get("epochs", 1)))))
        eta_min = float(params.get("eta_min", 1e-6))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_max, eta_min=eta_min)
        return SchedulerBundle(scheduler=scheduler, step_mode="epoch")

    if scheduler_name == "reducelronplateau":
        mode = "max" if bool(config.get("maximize_metric", True)) else "min"
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode=mode,
            factor=float(params.get("factor", 0.5)),
            patience=int(params.get("patience", 2)),
            threshold=float(params.get("threshold", 1e-4)),
            min_lr=float(params.get("min_lr", 1e-7)),
        )
        return SchedulerBundle(scheduler=scheduler, step_mode="metric")

    if scheduler_name == "onecyclelr":
        if steps_per_epoch <= 0:
            raise ValueError("OneCycleLR requires steps_per_epoch > 0")

        max_lr = float(params.get("max_lr", config.get("learning_rate", 3e-4)))
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=max_lr,
            epochs=int(config.get("epochs", 1)),
            steps_per_epoch=steps_per_epoch,
            pct_start=float(params.get("pct_start", 0.3)),
            div_factor=float(params.get("div_factor", 25.0)),
            final_div_factor=float(params.get("final_div_factor", 10000.0)),
            anneal_strategy=str(params.get("anneal_strategy", "cos")),
        )
        return SchedulerBundle(scheduler=scheduler, step_mode="batch")

    raise ValueError("Unsupported scheduler. Use one of: StepLR, CosineAnnealingLR, ReduceLROnPlateau, OneCycleLR")


def step_scheduler(bundle: SchedulerBundle, metric_value: Optional[float] = None) -> None:
    """Step configured scheduler according to its step mode."""
    if bundle.scheduler is None or bundle.step_mode == "none":
        return

    if bundle.step_mode == "metric":
        if metric_value is None:
            raise ValueError("Metric-based scheduler requires metric_value")
        bundle.scheduler.step(metric_value)
    else:
        bundle.scheduler.step()
