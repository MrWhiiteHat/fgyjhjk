"""EfficientNet backbones for binary face classification."""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision import models


class EfficientNetBinaryClassifier(nn.Module):
    """EfficientNet-B0/B3 classifier with configurable binary head."""

    def __init__(
        self,
        variant: str = "efficientnet_b0",
        pretrained: bool = True,
        dropout: float = 0.2,
        hidden_dim: int = 512,
        freeze_backbone: bool = False,
    ) -> None:
        super().__init__()

        key = str(variant).strip().lower()
        if key == "efficientnet_b3":
            weights = models.EfficientNet_B3_Weights.DEFAULT if pretrained else None
            backbone = models.efficientnet_b3(weights=weights)
        else:
            weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
            backbone = models.efficientnet_b0(weights=weights)

        in_features = int(backbone.classifier[1].in_features)
        backbone.classifier = nn.Identity()

        self.backbone = backbone
        self.classifier = nn.Sequential(
            nn.Dropout(float(dropout)),
            nn.Linear(in_features, int(hidden_dim)),
            nn.ReLU(inplace=True),
            nn.Dropout(float(dropout)),
            nn.Linear(int(hidden_dim), 1),
        )

        self.set_backbone_trainable(not freeze_backbone)

    def set_backbone_trainable(self, trainable: bool) -> None:
        """Freeze or unfreeze all backbone parameters."""
        for param in self.backbone.parameters():
            param.requires_grad = bool(trainable)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Run forward pass and return flattened logit tensor."""
        features = self.backbone(inputs)
        logits = self.classifier(features).view(-1)
        return logits
