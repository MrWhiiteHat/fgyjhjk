"""Vision Transformer backbone for binary face classification."""

from __future__ import annotations

import torch
import torch.nn as nn


class ViTBinaryClassifier(nn.Module):
    """Timm ViT model adapted to output a single binary logit."""

    def __init__(
        self,
        variant: str = "vit_base_patch16_224",
        pretrained: bool = True,
        dropout: float = 0.2,
        hidden_dim: int = 512,
        freeze_backbone: bool = False,
    ) -> None:
        super().__init__()

        try:
            import timm
        except Exception as exc:
            raise ImportError("timm is required for ViT backbone. Install training/requirements.txt") from exc

        model_name = str(variant).strip().lower() or "vit_base_patch16_224"
        self.backbone = timm.create_model(
            model_name,
            pretrained=bool(pretrained),
            num_classes=0,
            global_pool="avg",
        )
        in_features = int(getattr(self.backbone, "num_features", hidden_dim))

        self.classifier = nn.Sequential(
            nn.Dropout(float(dropout)),
            nn.Linear(in_features, int(hidden_dim)),
            nn.GELU(),
            nn.Dropout(float(dropout)),
            nn.Linear(int(hidden_dim), 1),
        )

        self.set_backbone_trainable(not freeze_backbone)

    def set_backbone_trainable(self, trainable: bool) -> None:
        """Freeze or unfreeze backbone feature extractor parameters."""
        for param in self.backbone.parameters():
            param.requires_grad = bool(trainable)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Run forward pass and return flattened binary logits."""
        features = self.backbone(inputs)
        logits = self.classifier(features).view(-1)
        return logits
