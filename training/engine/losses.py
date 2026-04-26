"""Loss functions for binary real-vs-fake classification."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class BinaryFocalLoss(nn.Module):
    """Numerically stable focal loss for binary logits with optional class weighting."""

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
        class_weights: Optional[list[float]] = None,
    ) -> None:
        super().__init__()
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.label_smoothing = float(label_smoothing)
        self.class_weights = class_weights if class_weights and len(class_weights) == 2 else None

    def _smooth_targets(self, targets: torch.Tensor) -> torch.Tensor:
        """Apply binary label smoothing towards 0.5 target probability."""
        if self.label_smoothing <= 0:
            return targets
        smooth = self.label_smoothing
        return targets * (1.0 - smooth) + 0.5 * smooth

    def _sample_weights(self, targets: torch.Tensor) -> Optional[torch.Tensor]:
        """Build per-sample class weights from [real_weight, fake_weight]."""
        if self.class_weights is None:
            return None
        weight_real = float(self.class_weights[0])
        weight_fake = float(self.class_weights[1])
        return targets * weight_fake + (1.0 - targets) * weight_real

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute focal loss from logits and binary targets."""
        logits = logits.view(-1)
        targets = targets.float().view(-1)
        targets = self._smooth_targets(targets)

        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probs = torch.sigmoid(logits)
        pt = targets * probs + (1.0 - targets) * (1.0 - probs)

        alpha_t = targets * self.alpha + (1.0 - targets) * (1.0 - self.alpha)
        focal_factor = alpha_t * torch.pow(1.0 - pt, self.gamma)
        loss = focal_factor * bce

        sample_weights = self._sample_weights(targets)
        if sample_weights is not None:
            loss = loss * sample_weights

        return loss.mean()


class BinaryClassificationLoss(nn.Module):
    """Configurable binary loss supporting BCE, weighted BCE, and focal variants."""

    def __init__(
        self,
        loss_name: str,
        class_weights: Optional[list[float]],
        label_smoothing: float,
        use_focal_loss: bool,
        focal_params: Optional[Dict],
    ) -> None:
        super().__init__()

        self.loss_name = str(loss_name).strip().lower()
        self.class_weights = class_weights if class_weights and len(class_weights) == 2 else None
        self.label_smoothing = float(label_smoothing)

        if use_focal_loss:
            self.loss_name = "focal"

        focal_cfg = focal_params or {}
        self.focal = BinaryFocalLoss(
            alpha=float(focal_cfg.get("alpha", 0.25)),
            gamma=float(focal_cfg.get("gamma", 2.0)),
            label_smoothing=self.label_smoothing,
            class_weights=self.class_weights,
        )

    def _smooth_targets(self, targets: torch.Tensor) -> torch.Tensor:
        """Apply binary label smoothing to reduce over-confidence."""
        if self.label_smoothing <= 0:
            return targets
        smooth = self.label_smoothing
        return targets * (1.0 - smooth) + 0.5 * smooth

    def _weighted_bce_loss(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute weighted BCE loss using per-sample class multipliers."""
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")

        if self.class_weights and len(self.class_weights) == 2:
            w_real = float(self.class_weights[0])
            w_fake = float(self.class_weights[1])
            sample_weights = targets * w_fake + (1.0 - targets) * w_real
            bce = bce * sample_weights

        return bce.mean()

    def _bce_with_logits_loss(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute BCEWithLogitsLoss with optional positive-class weighting."""
        if self.class_weights and len(self.class_weights) == 2:
            w_real = max(1e-12, float(self.class_weights[0]))
            w_fake = max(1e-12, float(self.class_weights[1]))
            pos_weight = torch.tensor([w_fake / w_real], dtype=logits.dtype, device=logits.device)
        else:
            pos_weight = None

        return F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pos_weight)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute selected loss from model logits and binary labels."""
        logits = logits.view(-1)
        targets = targets.float().view(-1)
        targets = self._smooth_targets(targets)

        if self.loss_name in {"focal", "focal_loss"}:
            return self.focal(logits, targets)
        if self.loss_name in {"weighted_bce", "weighted_bce_with_logits"}:
            return self._weighted_bce_loss(logits, targets)
        if self.loss_name in {"bce", "bce_with_logits", "bcewithlogitsloss"}:
            return self._bce_with_logits_loss(logits, targets)

        raise ValueError(
            f"Unsupported loss function '{self.loss_name}'. "
            "Use one of: bce_with_logits, weighted_bce, focal"
        )


def build_loss(config: Dict, logger: logging.Logger) -> nn.Module:
    """Build configured loss function and log guidance on imbalance strategy."""
    loss_name = str(config.get("loss_function", "bce_with_logits"))
    class_weights = config.get("class_weights", None)

    criterion = BinaryClassificationLoss(
        loss_name=loss_name,
        class_weights=class_weights,
        label_smoothing=float(config.get("label_smoothing", 0.0)),
        use_focal_loss=bool(config.get("use_focal_loss", False)),
        focal_params=config.get("focal_params", {}),
    )

    logger.info(
        "Loss initialized: %s | class_weights=%s | label_smoothing=%s | use_focal=%s",
        loss_name,
        class_weights,
        config.get("label_smoothing", 0.0),
        config.get("use_focal_loss", False),
    )
    logger.info(
        "Loss guidance: BCEWithLogitsLoss is stable baseline; weighted BCE helps class imbalance; "
        "focal loss helps hard-example focus when many easy negatives dominate."
    )
    return criterion
