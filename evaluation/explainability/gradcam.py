"""Grad-CAM implementation for binary real-vs-fake classifier explainability."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import torch

from evaluation.explainability.overlay_utils import normalize_heatmap


class GradCAM:
    """Generate Grad-CAM heatmaps from CNN-like target layers."""

    def __init__(self, model: torch.nn.Module, target_layer: str, logger: logging.Logger) -> None:
        self.model = model
        self.target_layer_name = str(target_layer)
        self.logger = logger

        self._forward_handle: Optional[Any] = None
        self._backward_handle: Optional[Any] = None

        self.activations: Optional[torch.Tensor] = None
        self.gradients: Optional[torch.Tensor] = None

        self.target_layer_module = self._resolve_target_layer(self.target_layer_name)
        self._register_hooks()

    def _resolve_target_layer(self, target_layer: str) -> torch.nn.Module:
        """Resolve dotted target layer path on model modules."""
        module: Any = self.model
        for token in target_layer.split("."):
            if not hasattr(module, token):
                raise ValueError(
                    f"Grad-CAM target layer '{target_layer}' not found on model. "
                    f"Failed at token '{token}'."
                )
            module = getattr(module, token)

        if not isinstance(module, torch.nn.Module):
            raise TypeError(f"Resolved target layer is not torch.nn.Module: {target_layer}")

        return module

    def _register_hooks(self) -> None:
        """Register forward/backward hooks on target layer."""

        def forward_hook(_module, _input, output):
            self.activations = output.detach()

        def backward_hook(_module, _grad_input, grad_output):
            if isinstance(grad_output, tuple) and grad_output:
                self.gradients = grad_output[0].detach()
            elif torch.is_tensor(grad_output):
                self.gradients = grad_output.detach()
            else:
                self.gradients = None

        self._forward_handle = self.target_layer_module.register_forward_hook(forward_hook)
        self._backward_handle = self.target_layer_module.register_full_backward_hook(backward_hook)

    def remove_hooks(self) -> None:
        """Remove hooks to avoid accumulating graph references."""
        if self._forward_handle is not None:
            self._forward_handle.remove()
            self._forward_handle = None

        if self._backward_handle is not None:
            self._backward_handle.remove()
            self._backward_handle = None

    def generate(self, input_tensor: torch.Tensor, target_class: int = 1) -> np.ndarray:
        """Generate a single heatmap for one input sample."""
        if input_tensor.ndim != 4 or input_tensor.shape[0] != 1:
            raise ValueError("Grad-CAM currently supports batch size 1 input of shape [1,C,H,W]")

        if not isinstance(self.model, torch.nn.Module):
            raise TypeError("Grad-CAM requires a torch.nn.Module backend")

        self.model.zero_grad(set_to_none=True)
        logits = self.model(input_tensor)

        if not torch.is_tensor(logits):
            raise RuntimeError("Model output is not a tensor")

        flat_logits = logits.view(-1)
        if flat_logits.numel() < 1:
            raise RuntimeError("Model output tensor is empty")

        score = flat_logits[0] if int(target_class) == 1 else -flat_logits[0]
        score.backward(retain_graph=False)

        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients")

        if self.activations.ndim != 4 or self.gradients.ndim != 4:
            raise RuntimeError(
                "Grad-CAM target layer must produce 4D feature maps. "
                "This target appears unsupported (possibly transformer token outputs)."
            )

        weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)
        cam = torch.sum(weights * self.activations, dim=1)
        cam = torch.relu(cam)

        cam_np = cam.detach().cpu().numpy()[0]
        normalized = normalize_heatmap(cam_np)

        if float(np.max(normalized)) <= 1e-8:
            raise RuntimeError(
                "Grad-CAM map is all zeros. Choose a different target layer or verify gradient flow."
            )

        return normalized

    def __del__(self) -> None:
        """Ensure hooks are removed during object cleanup."""
        try:
            self.remove_hooks()
        except Exception:
            pass
