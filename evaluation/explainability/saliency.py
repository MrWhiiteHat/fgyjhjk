"""Input-gradient saliency maps for binary classifier explainability."""

from __future__ import annotations

import numpy as np
import torch

from evaluation.explainability.overlay_utils import normalize_heatmap


class SaliencyExplainer:
    """Compute absolute input-gradient saliency for batch size 1 samples."""

    def __init__(self, model: torch.nn.Module) -> None:
        self.model = model

    def generate(self, input_tensor: torch.Tensor, target_class: int = 1) -> np.ndarray:
        """Generate saliency map for one input tensor."""
        if input_tensor.ndim != 4 or input_tensor.shape[0] != 1:
            raise ValueError("Saliency currently supports input shape [1,C,H,W]")

        if not isinstance(self.model, torch.nn.Module):
            raise TypeError("Saliency requires a torch.nn.Module backend")

        tensor = input_tensor.clone().detach().requires_grad_(True)
        self.model.zero_grad(set_to_none=True)

        logits = self.model(tensor)
        if not torch.is_tensor(logits):
            raise RuntimeError("Model output is not tensor")

        flat_logits = logits.view(-1)
        if flat_logits.numel() < 1:
            raise RuntimeError("Model output tensor is empty")

        score = flat_logits[0] if int(target_class) == 1 else -flat_logits[0]
        score.backward(retain_graph=False)

        if tensor.grad is None:
            raise RuntimeError("No input gradients available for saliency")

        gradients = tensor.grad.detach().abs()
        if gradients.ndim != 4:
            raise RuntimeError(f"Unexpected saliency gradient shape: {tuple(gradients.shape)}")

        saliency = gradients.max(dim=1).values[0]
        saliency_np = saliency.detach().cpu().numpy()
        normalized = normalize_heatmap(saliency_np)

        if float(np.max(normalized)) <= 1e-8:
            raise RuntimeError("Saliency map is all zeros. Gradient signal is too weak for this sample.")

        return normalized
