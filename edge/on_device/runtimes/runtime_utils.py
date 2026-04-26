"""Common runtime interfaces and postprocessing helpers for edge inference."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


class EdgeRuntime(Protocol):
    """Standardized edge runtime interface."""

    def load_model(self) -> None: ...
    def preprocess_input(self, media_path: str) -> np.ndarray: ...
    def run_inference(self, model_input: np.ndarray) -> Any: ...
    def postprocess_output(self, output: Any) -> dict[str, Any]: ...
    def unload_model(self) -> None: ...


@dataclass
class RuntimeMetadata:
    """Metadata about a loaded runtime and model."""

    runtime_name: str
    model_path: str
    model_loaded: bool
    supports_quantized: bool
    input_layout: str


def softmax(logits: np.ndarray) -> np.ndarray:
    """Compute numerically stable softmax."""
    max_values = np.max(logits, axis=-1, keepdims=True)
    exps = np.exp(logits - max_values)
    return exps / np.sum(exps, axis=-1, keepdims=True)


def now_ms() -> float:
    """High precision timer in milliseconds."""
    return time.perf_counter() * 1000.0


def build_prediction_payload(
    probs: np.ndarray,
    threshold: float,
    label_real: str = "REAL",
    label_fake: str = "FAKE",
    model_source: str = "edge",
    inference_time_ms: float = 0.0,
) -> dict[str, Any]:
    """Standardized prediction payload aligned with backend contract style."""
    if probs.ndim > 1:
        probs = probs.reshape(-1)
    if probs.size == 1:
        fake_prob = float(probs[0])
        real_prob = float(1.0 - fake_prob)
    else:
        real_prob = float(probs[0])
        fake_prob = float(probs[1])

    predicted_label = label_fake if fake_prob >= float(threshold) else label_real
    confidence = fake_prob if predicted_label == label_fake else real_prob

    return {
        "predicted_label": predicted_label,
        "predicted_probability": round(float(confidence), 6),
        "probabilities": {
            label_real: round(real_prob, 6),
            label_fake: round(fake_prob, 6),
        },
        "threshold": float(threshold),
        "model_source": model_source,
        "inference_time_ms": round(float(inference_time_ms), 3),
    }
