"""Optimizer builders for binary training pipeline."""

from __future__ import annotations

import logging
from typing import Dict, List

import torch


def _build_parameter_groups(model: torch.nn.Module, config: Dict, logger: logging.Logger) -> List[Dict]:
    """Build parameter groups with optional backbone/head learning rate split."""
    params_cfg = config.get("optimizer_params", {}) or {}
    backbone_lr = params_cfg.get("backbone_lr", None)
    head_lr = params_cfg.get("head_lr", None)

    if backbone_lr is None or head_lr is None:
        return [{"params": [p for p in model.parameters() if p.requires_grad]}]

    if not hasattr(model, "backbone") or not hasattr(model, "classifier"):
        logger.warning("Model missing backbone/classifier attributes. Falling back to single LR parameter group.")
        return [{"params": [p for p in model.parameters() if p.requires_grad]}]

    backbone_params = [p for p in model.backbone.parameters() if p.requires_grad]
    head_params = [p for p in model.classifier.parameters() if p.requires_grad]

    groups = []
    if backbone_params:
        groups.append({"params": backbone_params, "lr": float(backbone_lr)})
    if head_params:
        groups.append({"params": head_params, "lr": float(head_lr)})

    logger.info("Optimizer parameter groups configured: backbone_lr=%s head_lr=%s", backbone_lr, head_lr)
    return groups


def build_optimizer(model: torch.nn.Module, config: Dict, logger: logging.Logger) -> torch.optim.Optimizer:
    """Instantiate configured optimizer with validation and weight decay support."""
    optimizer_name = str(config.get("optimizer", "adamw")).strip().lower()
    learning_rate = float(config.get("learning_rate", 3e-4))
    weight_decay = float(config.get("weight_decay", 0.0))

    param_groups = _build_parameter_groups(model, config, logger)

    if optimizer_name == "adam":
        optimizer = torch.optim.Adam(param_groups, lr=learning_rate, weight_decay=weight_decay)
    elif optimizer_name == "adamw":
        optimizer = torch.optim.AdamW(param_groups, lr=learning_rate, weight_decay=weight_decay)
    elif optimizer_name == "sgd":
        momentum = float(config.get("optimizer_params", {}).get("momentum", 0.9))
        optimizer = torch.optim.SGD(
            param_groups,
            lr=learning_rate,
            weight_decay=weight_decay,
            momentum=momentum,
            nesterov=True,
        )
    else:
        raise ValueError("Unsupported optimizer. Use one of: adam, adamw, sgd")

    logger.info(
        "Optimizer initialized: %s | lr=%s | weight_decay=%s",
        optimizer_name,
        learning_rate,
        weight_decay,
    )
    return optimizer
