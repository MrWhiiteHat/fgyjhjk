from __future__ import annotations

from dataclasses import dataclass

from edge.on_device.model_conversion.benchmark_edge_models import benchmark_runtime


@dataclass
class _Meta:
    runtime_name: str
    model_path: str


class _FakeRuntime:
    def __init__(self) -> None:
        self.loaded = False
        self.predict_calls = 0

    def load_model(self) -> None:
        self.loaded = True

    def unload_model(self) -> None:
        self.loaded = False

    def predict(self, _image_path: str) -> dict:
        self.predict_calls += 1
        return {
            "predicted_label": "REAL",
            "predicted_probability": 0.92,
            "probabilities": {"REAL": 0.92, "FAKE": 0.08},
        }

    def get_metadata(self) -> _Meta:
        return _Meta(runtime_name="fake_runtime", model_path="fake_model.bin")


def test_benchmark_runtime_returns_expected_fields() -> None:
    runtime = _FakeRuntime()
    report = benchmark_runtime(runtime, image_path="unused.jpg", runs=4, warmup=1)

    assert report["runtime"] == "fake_runtime"
    assert report["model_path"] == "fake_model.bin"
    assert report["runs"] == 4
    assert report["warmup"] == 1
    assert report["latency_ms_mean"] >= 0
    assert report["sample_prediction"]["predicted_label"] == "REAL"
    assert runtime.loaded is False
