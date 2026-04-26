"""Build retraining datasets from baseline, fresh, and corrected feedback data."""

from __future__ import annotations

from dataclasses import dataclass, field

from ml_lifecycle.feedback.label_store import CorrectedLabel


@dataclass
class TrainingSample:
    """Standardized sample used for retraining."""

    sample_id: str
    features: dict[str, float]
    label: int
    source: str
    metadata: dict[str, str] = field(default_factory=dict)


class DatasetBuilder:
    """Combines original, new, and corrected samples into one training set."""

    def build_dataset(
        self,
        *,
        original_samples: list[dict],
        new_samples: list[dict],
        corrected_labels: list[CorrectedLabel],
    ) -> list[TrainingSample]:
        """Build merged training dataset and apply corrected labels by prediction id."""

        merged: dict[str, TrainingSample] = {}

        def normalize(source_samples: list[dict], source_name: str) -> None:
            for sample in source_samples:
                sample_id = str(sample.get("sample_id") or sample.get("prediction_id") or "").strip()
                features = dict(sample.get("features") or {})
                label = sample.get("label")
                if not sample_id or label is None:
                    continue
                merged[sample_id] = TrainingSample(
                    sample_id=sample_id,
                    features={k: float(v) for k, v in features.items()},
                    label=int(label),
                    source=source_name,
                    metadata={k: str(v) for k, v in (sample.get("metadata") or {}).items()},
                )

        normalize(original_samples, "original")
        normalize(new_samples, "new")

        for corrected in corrected_labels:
            sid = str(corrected.prediction_id)
            if sid in merged:
                sample = merged[sid]
                merged[sid] = TrainingSample(
                    sample_id=sample.sample_id,
                    features=sample.features,
                    label=int(corrected.corrected_label),
                    source="corrected_feedback",
                    metadata={**sample.metadata, "corrected_from": corrected.model_version},
                )

        return list(merged.values())
