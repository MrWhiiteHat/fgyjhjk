from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

from edge.on_device.runtimes.tflite_runtime import TFLiteRuntimeWrapper


class FakeInterpreter:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._last_tensor = None

    def allocate_tensors(self) -> None:
        return None

    def get_input_details(self):
        return [{"index": 0}]

    def get_output_details(self):
        return [{"index": 1}]

    def set_tensor(self, index: int, tensor: np.ndarray) -> None:
        assert index == 0
        self._last_tensor = tensor

    def invoke(self) -> None:
        return None

    def get_tensor(self, index: int) -> np.ndarray:
        assert index == 1
        return np.asarray([[0.2, 0.8]], dtype=np.float32)


def _install_fake_tflite_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = types.ModuleType("tflite_runtime")
    interpreter_mod = types.ModuleType("tflite_runtime.interpreter")
    interpreter_mod.Interpreter = FakeInterpreter
    monkeypatch.setitem(sys.modules, "tflite_runtime", pkg)
    monkeypatch.setitem(sys.modules, "tflite_runtime.interpreter", interpreter_mod)


def test_tflite_wrapper_load_and_infer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_tflite_runtime(monkeypatch)
    model_path = tmp_path / "model.tflite"
    model_path.write_bytes(b"stub")

    runtime = TFLiteRuntimeWrapper(model_path=str(model_path), tensor_layout="nhwc", threshold=0.5)
    runtime.load_model()

    model_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
    output = runtime.run_inference(model_input)
    payload = runtime.postprocess_output(output)
    metadata = runtime.get_metadata()

    assert output.shape == (1, 2)
    assert payload["predicted_label"] == "FAKE"
    assert payload["probabilities"]["FAKE"] == pytest.approx(0.8)
    assert metadata.runtime_name == "tflite_runtime"
    assert metadata.model_loaded is True

    runtime.unload_model()
    assert runtime.interpreter is None


def test_tflite_run_without_load_raises(tmp_path: Path) -> None:
    model_path = tmp_path / "model.tflite"
    model_path.write_bytes(b"stub")

    runtime = TFLiteRuntimeWrapper(model_path=str(model_path))
    with pytest.raises(RuntimeError):
        runtime.run_inference(np.zeros((1, 224, 224, 3), dtype=np.float32))
