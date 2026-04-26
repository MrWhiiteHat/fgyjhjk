"""TFLite runtime wrapper with safe backend fallback behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from edge.on_device.preprocessing.image_preprocess import preprocess_image_for_model
from edge.on_device.runtimes.runtime_utils import RuntimeMetadata, build_prediction_payload, now_ms


class TFLiteRuntimeWrapper:
    """Wraps TensorFlow Lite interpreter behind a standard interface."""

    def __init__(
        self,
        model_path: str,
        input_size: tuple[int, int] = (224, 224),
        threshold: float = 0.5,
        tensor_layout: str = "nhwc",
    ) -> None:
        self.model_path = str(model_path)
        self.input_size = input_size
        self.threshold = float(threshold)
        self.tensor_layout = tensor_layout
        self.interpreter = None
        self.input_index = None
        self.output_index = None
        self._runtime_name = "tflite_runtime"

    def load_model(self) -> None:
        path = Path(self.model_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"TFLite model not found: {path}")

        interpreter_cls = None
        try:
            from tflite_runtime.interpreter import Interpreter  # type: ignore[import-not-found]

            interpreter_cls = Interpreter
        except Exception:
            try:
                from tensorflow.lite.python.interpreter import Interpreter  # type: ignore[import-not-found]

                interpreter_cls = Interpreter
                self._runtime_name = "tensorflow_lite"
            except Exception as exc:
                raise RuntimeError("Neither tflite_runtime nor tensorflow lite interpreter is available") from exc

        self.interpreter = interpreter_cls(model_path=str(path))
        self.interpreter.allocate_tensors()
        self.input_index = int(self.interpreter.get_input_details()[0]["index"])
        self.output_index = int(self.interpreter.get_output_details()[0]["index"])

    def preprocess_input(self, media_path: str) -> np.ndarray:
        return preprocess_image_for_model(
            image_path=media_path,
            input_size=self.input_size,
            tensor_layout=self.tensor_layout,
        )

    def run_inference(self, model_input: np.ndarray) -> Any:
        if self.interpreter is None or self.input_index is None or self.output_index is None:
            raise RuntimeError("Model is not loaded")
        self.interpreter.set_tensor(self.input_index, model_input.astype(np.float32))
        self.interpreter.invoke()
        return self.interpreter.get_tensor(self.output_index)

    def postprocess_output(self, output: Any) -> dict[str, Any]:
        probs = np.asarray(output, dtype=np.float32).reshape(-1)
        return build_prediction_payload(
            probs=probs,
            threshold=self.threshold,
            model_source="tflite_local",
        )

    def unload_model(self) -> None:
        self.interpreter = None
        self.input_index = None
        self.output_index = None

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_name=self._runtime_name,
            model_path=self.model_path,
            model_loaded=self.interpreter is not None,
            supports_quantized=True,
            input_layout=self.tensor_layout,
        )

    def predict(self, image_path: str) -> dict[str, Any]:
        """Convenience prediction API with timing."""
        start_ms = now_ms()
        model_input = self.preprocess_input(image_path)
        output = self.run_inference(model_input)
        payload = self.postprocess_output(output)
        payload["inference_time_ms"] = round(now_ms() - start_ms, 3)
        return payload
