"""Continuous retraining pipeline with real model fitting."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from ml_lifecycle.feedback.label_store import CorrectedLabel
from ml_lifecycle.retraining.data_validation import DataValidation, ValidationResult
from ml_lifecycle.retraining.dataset_builder import DatasetBuilder, TrainingSample


@dataclass
class TrainedLinearModel:
    """Binary logistic regression model trained via gradient descent."""

    feature_names: list[str]
    weights: list[float]
    bias: float

    def predict_proba(self, features: dict[str, float]) -> float:
        """Predict class-1 probability from feature map."""

        x = [float(features.get(name, 0.0)) for name in self.feature_names]
        score = sum(w * xi for w, xi in zip(self.weights, x)) + self.bias
        return 1.0 / (1.0 + math.exp(-max(min(score, 35.0), -35.0)))

    def predict(self, features: dict[str, float], threshold: float = 0.5) -> int:
        """Predict binary class label."""

        return 1 if self.predict_proba(features) >= threshold else 0

    def to_artifact_bytes(self) -> bytes:
        """Serialize model artifact payload."""

        payload = {
            "feature_names": self.feature_names,
            "weights": self.weights,
            "bias": self.bias,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class RetrainPipeline:
    """Constructs data, validates it, and retrains a binary model."""

    def __init__(self, dataset_builder: DatasetBuilder | None = None, validator: DataValidation | None = None) -> None:
        self._builder = dataset_builder or DatasetBuilder()
        self._validator = validator or DataValidation()

    def run(
        self,
        *,
        original_samples: list[dict],
        new_samples: list[dict],
        corrected_labels: list[CorrectedLabel],
        config: dict,
    ) -> dict:
        """Run end-to-end retraining and return candidate model artifacts and metrics."""

        merged = self._builder.build_dataset(
            original_samples=original_samples,
            new_samples=new_samples,
            corrected_labels=corrected_labels,
        )

        validation_cfg = dict(config.get("validation") or {})
        validation: ValidationResult = self._validator.clean_and_validate(
            samples=merged,
            min_samples=int(validation_cfg.get("min_samples", 100)),
            min_class_ratio=float(validation_cfg.get("min_class_ratio", 0.2)),
            max_class_ratio=float(validation_cfg.get("max_class_ratio", 0.8)),
        )
        if not validation.is_valid:
            raise ValueError(f"Retraining dataset validation failed: {validation.reason}")

        model = self._train_logistic_regression(validation.cleaned_samples)
        train_accuracy = self._accuracy(model, validation.cleaned_samples)

        dataset_id = self._compute_dataset_id(validation.cleaned_samples)
        return {
            "model": model,
            "artifact_bytes": model.to_artifact_bytes(),
            "training_dataset_id": dataset_id,
            "metrics": {
                "train_accuracy": train_accuracy,
                "num_samples": len(validation.cleaned_samples),
                "dropped_samples": validation.dropped_samples,
            },
            "class_distribution": validation.class_distribution,
        }

    def _train_logistic_regression(self, samples: list[TrainingSample], epochs: int = 250, lr: float = 0.05) -> TrainedLinearModel:
        feature_names = sorted({name for sample in samples for name in sample.features.keys()})
        if not feature_names:
            raise ValueError("No features available for training")

        weights = [0.0 for _ in feature_names]
        bias = 0.0

        for _ in range(int(epochs)):
            grad_w = [0.0 for _ in feature_names]
            grad_b = 0.0

            for sample in samples:
                x = [float(sample.features.get(name, 0.0)) for name in feature_names]
                y = float(sample.label)

                score = sum(w * xi for w, xi in zip(weights, x)) + bias
                pred = 1.0 / (1.0 + math.exp(-max(min(score, 35.0), -35.0)))
                error = pred - y

                for idx, value in enumerate(x):
                    grad_w[idx] += error * value
                grad_b += error

            n = float(len(samples))
            for idx in range(len(weights)):
                weights[idx] -= lr * (grad_w[idx] / n)
            bias -= lr * (grad_b / n)

        return TrainedLinearModel(feature_names=feature_names, weights=weights, bias=bias)

    @staticmethod
    def _accuracy(model: TrainedLinearModel, samples: list[TrainingSample]) -> float:
        correct = 0
        for sample in samples:
            if model.predict(sample.features) == int(sample.label):
                correct += 1
        return correct / len(samples) if samples else 0.0

    @staticmethod
    def _compute_dataset_id(samples: list[TrainingSample]) -> str:
        ordered = sorted(samples, key=lambda item: item.sample_id)
        digest = 0
        for idx, sample in enumerate(ordered, start=1):
            digest ^= (hash(sample.sample_id) ^ hash(sample.label) ^ idx)
        return f"dataset_{abs(digest)}"
