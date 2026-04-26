"""ONNX runtime wrapper tuned for mobile/edge compatibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from edge.on_device.preprocessing.image_preprocess import preprocess_image_for_model
from edge.on_device.runtimes.runtime_utils import RuntimeMetadata, build_prediction_payload, now_ms


class ONNXRuntimeMobileWrapper:
    """ONNX Runtime wrapper with CPU-only default provider for portability."""

    def __init__(
        self,
        model_path: str,
        input_size: tuple[int, int] = (224, 224),
        threshold: float = 0.5,
        tensor_layout: str = "nchw",
    ) -> None:
        self.model_path = str(model_path)
        self.input_size = input_size
        self.threshold = float(threshold)
        self.tensor_layout = tensor_layout
        self.session = None
        self.input_name = None
        self.output_name = None

    def load_model(self) -> None:
        path = Path(self.model_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"ONNX model not found: {path}")
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise RuntimeError("onnxruntime is not installed") from exc

        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.input_name = str(self.session.get_inputs()[0].name)
        self.output_name = str(self.session.get_outputs()[0].name)

    def preprocess_input(self, media_path: str) -> np.ndarray:
        return preprocess_image_for_model(
            image_path=media_path,
            input_size=self.input_size,
            tensor_layout=self.tensor_layout,
        )

    def run_inference(self, model_input: np.ndarray) -> Any:
        if self.session is None or self.input_name is None or self.output_name is None:
            raise RuntimeError("Model is not loaded")
        outputs = self.session.run([self.output_name], {self.input_name: model_input.astype(np.float32)})
        return outputs[0]

    def postprocess_output(self, output: Any) -> dict[str, Any]:
        probs = np.asarray(output, dtype=np.float32).reshape(-1)
        return build_prediction_payload(
            probs=probs,
            threshold=self.threshold,
            model_source="onnx_local",
        )

    def unload_model(self) -> None:
        self.session = None
        self.input_name = None
        self.output_name = None

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_name="onnxruntime",
            model_path=self.model_path,
            model_loaded=self.session is not None,
            supports_quantized=True,
            input_layout=self.tensor_layout,
        )

    def predict(self, image_path: str) -> dict[str, Any]:
        start_ms = now_ms()
        model_input = self.preprocess_input(image_path)
        output = self.run_inference(model_input)
        payload = self.postprocess_output(output)
        payload["inference_time_ms"] = round(now_ms() - start_ms, 3)
        return payload
