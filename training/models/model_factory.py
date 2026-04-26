"""Factory for building supported binary-classification model backbones."""

from __future__ import annotations

import logging
from typing import Dict

import torch.nn as nn

from training.models.efficientnet_model import EfficientNetBinaryClassifier
from training.models.resnet_model import ResNetBinaryClassifier
from training.models.vit_model import ViTBinaryClassifier
from training.models.xception_model import XceptionBinaryClassifier


def create_model(config: Dict, logger: logging.Logger) -> nn.Module:
    """Instantiate model from config and validate supported backbone names."""
    backbone = str(config.get("backbone", "resnet50")).strip().lower()
    pretrained = bool(config.get("pretrained", True))
    freeze_backbone = bool(config.get("freeze_backbone", False))
    dropout = float(config.get("dropout", 0.2))
    hidden_dim = int(config.get("hidden_dim", 512))

    if backbone == "resnet50":
        model = ResNetBinaryClassifier(
            pretrained=pretrained,
            dropout=dropout,
            hidden_dim=hidden_dim,
            freeze_backbone=freeze_backbone,
        )
    elif backbone in {"efficientnet_b0", "efficientnet-b0"}:
        model = EfficientNetBinaryClassifier(
            variant="efficientnet_b0",
            pretrained=pretrained,
            dropout=dropout,
            hidden_dim=hidden_dim,
            freeze_backbone=freeze_backbone,
        )
    elif backbone in {"efficientnet_b3", "efficientnet-b3"}:
        model = EfficientNetBinaryClassifier(
            variant="efficientnet_b3",
            pretrained=pretrained,
            dropout=dropout,
            hidden_dim=hidden_dim,
            freeze_backbone=freeze_backbone,
        )
    elif backbone == "xception":
        model = XceptionBinaryClassifier(
            pretrained=pretrained,
            dropout=dropout,
            hidden_dim=hidden_dim,
            freeze_backbone=freeze_backbone,
        )
    elif backbone in {"vit", "vit_base_patch16_224"}:
        model = ViTBinaryClassifier(
            variant="vit_base_patch16_224",
            pretrained=pretrained,
            dropout=dropout,
            hidden_dim=hidden_dim,
            freeze_backbone=freeze_backbone,
        )
    else:
        supported = ["resnet50", "efficientnet_b0", "efficientnet_b3", "xception", "vit_base_patch16_224"]
        raise ValueError(f"Unsupported backbone '{backbone}'. Supported backbones: {supported}")

    logger.info("Created model backbone: %s", backbone)
    return model
