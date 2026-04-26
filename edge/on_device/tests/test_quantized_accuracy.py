from __future__ import annotations

from pathlib import Path

import pytest

from edge.on_device.model_conversion import validate_edge_model


class _FakeRuntime:
    def __init__(self, predictions_by_path: dict[str, float]) -> None:
        self.predictions_by_path = predictions_by_path
        self.loaded = False

    def load_model(self) -> None:
        self.loaded = True

    def unload_model(self) -> None:
        self.loaded = False

    def predict(self, image_path: str) -> dict:
        fake_prob = self.predictions_by_path[image_path]
        return {
            "probabilities": {
                "FAKE": fake_prob,
                "REAL": 1.0 - fake_prob,
            }
        }


def _write_reference_csv(path: Path, values: dict[str, float]) -> None:
    rows = ["image_path,fake_probability"]
    rows.extend([f"{image},{value}" for image, value in values.items()])
    path.write_text("\n".join(rows), encoding="utf-8")


def test_validate_model_passes_within_tolerance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expected = {
        "sample_a.jpg": 0.20,
        "sample_b.jpg": 0.80,
    }
    observed = {
        "sample_a.jpg": 0.22,
        "sample_b.jpg": 0.77,
    }

    reference = tmp_path / "reference.csv"
    _write_reference_csv(reference, expected)

    fake_runtime = _FakeRuntime(observed)
    monkeypatch.setattr(validate_edge_model, "_runtime_from_args", lambda runtime_kind, model_path: fake_runtime)

    report = validate_edge_model.validate_model(
        runtime_kind="onnx",
        model_path="unused.onnx",
        reference_file=str(reference),
        max_samples=10,
        abs_prob_tolerance=0.05,
    )

    assert report["pass"] is True
    assert report["successful_samples"] == 2
    assert report["average_abs_deviation"] is not None


def test_validate_model_fails_when_deviation_exceeds_tolerance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expected = {
        "sample_a.jpg": 0.20,
        "sample_b.jpg": 0.80,
    }
    observed = {
        "sample_a.jpg": 0.05,
        "sample_b.jpg": 0.20,
    }

    reference = tmp_path / "reference.csv"
    _write_reference_csv(reference, expected)

    fake_runtime = _FakeRuntime(observed)
    monkeypatch.setattr(validate_edge_model, "_runtime_from_args", lambda runtime_kind, model_path: fake_runtime)

    report = validate_edge_model.validate_model(
        runtime_kind="onnx",
        model_path="unused.onnx",
        reference_file=str(reference),
        max_samples=10,
        abs_prob_tolerance=0.02,
    )

    assert report["pass"] is False
    assert len(report["failures"]) >= 1
