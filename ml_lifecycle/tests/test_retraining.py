"""Retraining trigger and pipeline tests."""

from __future__ import annotations

from ml_lifecycle.feedback.label_store import CorrectedLabel
from ml_lifecycle.retraining.retrain_pipeline import RetrainPipeline
from ml_lifecycle.retraining.training_trigger import TrainingTrigger


def _make_samples(prefix: str, count: int, label: int) -> list[dict]:
    samples: list[dict] = []
    for idx in range(count):
        base = 0.2 if label == 0 else 1.0
        samples.append(
            {
                "sample_id": f"{prefix}_{label}_{idx}",
                "features": {"x": base + (idx % 5) * 0.01, "y": base * 0.5 + (idx % 3) * 0.01},
                "label": label,
            }
        )
    return samples


def test_training_trigger_on_drift_and_feedback() -> None:
    trigger = TrainingTrigger()
    drift_report = {
        "data_drift": {"aggregate_score": 0.3},
        "concept_drift": {"confidence_shift": 0.15, "error_rate_delta": 0.08},
    }
    config = {
        "drift_trigger": {
            "data_drift_score_threshold": 0.2,
            "concept_confidence_shift_threshold": 0.1,
            "concept_error_rate_delta_threshold": 0.05,
        },
        "time_trigger": {"min_days_between_retrains": 7},
        "feedback_trigger": {"min_feedback_records": 20},
    }

    decision = trigger.should_trigger(
        drift_report=drift_report,
        last_retrain_at="2026-04-01T00:00:00+00:00",
        now_iso="2026-04-18T00:00:00+00:00",
        feedback_volume=25,
        config=config,
    )

    assert decision.should_trigger is True
    assert any(reason.startswith("drift:") for reason in decision.reasons)
    assert "feedback:volume_threshold" in decision.reasons


def test_retrain_pipeline_runs_real_training() -> None:
    pipeline = RetrainPipeline()

    original_samples = _make_samples("orig", 60, 0) + _make_samples("orig", 60, 1)
    new_samples = _make_samples("new", 20, 0) + _make_samples("new", 20, 1)

    corrected = [
        CorrectedLabel(
            prediction_id="new_0_3",
            corrected_label=1,
            model_version="1.0.0",
            updated_at="2026-04-18T00:00:00+00:00",
            source="feedback",
        )
    ]

    config = {
        "validation": {
            "min_samples": 100,
            "min_class_ratio": 0.2,
            "max_class_ratio": 0.8,
        }
    }

    output = pipeline.run(
        original_samples=original_samples,
        new_samples=new_samples,
        corrected_labels=corrected,
        config=config,
    )

    model = output["model"]
    assert output["metrics"]["num_samples"] >= 100
    assert output["metrics"]["train_accuracy"] >= 0.8
    assert model.predict({"x": 1.1, "y": 0.6}) == 1
    assert isinstance(output["artifact_bytes"], bytes)
