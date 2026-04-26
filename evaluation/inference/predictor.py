"""Unified predictor abstraction for binary real-vs-fake inference."""

from __future__ import annotations

import logging
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import torch

from evaluation.utils.checkpoint_loader import (
    ArtifactBundle,
    load_onnx_model,
    load_pytorch_model,
    load_torchscript_model,
    resolve_model_artifact,
    verify_model_forward_pass,
)
from evaluation.utils.device import can_use_amp, resolve_device, sync_device_if_needed
from evaluation.utils.helpers import class_index_to_name, summarize_latencies, to_probability_from_logit
from evaluation.utils.io import save_serializable_json


class Predictor:
    """Prediction runtime wrapper supporting PyTorch, TorchScript, and ONNX artifacts."""

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        strict_checkpoint_loading: bool = True,
    ) -> None:
        self.config = config
        self.logger = logger
        self.class_names = list(config.get("class_names", ["REAL", "FAKE"]))
        self.default_threshold = float(config.get("default_threshold", 0.5))

        self.device = resolve_device(str(config.get("device", "auto")), logger)
        self.use_amp = can_use_amp(bool(config.get("amp_inference", False)), self.device, logger)

        artifact_info = resolve_model_artifact(config, logger)
        self.artifact_type = str(artifact_info["artifact_type"])
        self.artifact_path = Path(artifact_info["artifact_path"])

        self.bundle: ArtifactBundle = self._load_artifact(
            artifact_type=self.artifact_type,
            artifact_path=self.artifact_path,
            strict_checkpoint_loading=strict_checkpoint_loading,
        )

        self.model = self.bundle.model
        self.model_name = self.bundle.model_name
        self.checkpoint_path = self.bundle.checkpoint_path or str(self.bundle.artifact_path.as_posix())
        self.threshold_from_artifact = float(self.bundle.threshold)

        verify_model_forward_pass(
            model=self.model,
            input_size=int(self.config.get("input_size", 224)),
            device=self.device,
            logger=self.logger,
        )

    def _load_artifact(
        self,
        artifact_type: str,
        artifact_path: Path,
        strict_checkpoint_loading: bool,
    ) -> ArtifactBundle:
        """Load model artifact according to resolved type."""
        if artifact_type == "pytorch":
            return load_pytorch_model(
                model_config=self.config,
                checkpoint_path=artifact_path,
                device=self.device,
                logger=self.logger,
                strict=bool(strict_checkpoint_loading),
            )
        if artifact_type == "torchscript":
            return load_torchscript_model(
                torchscript_path=artifact_path,
                device=self.device,
                logger=self.logger,
                default_threshold=float(self.config.get("default_threshold", 0.5)),
                config_snapshot=self.config,
            )
        if artifact_type == "onnx":
            return load_onnx_model(
                onnx_path=artifact_path,
                device=self.device,
                logger=self.logger,
                default_threshold=float(self.config.get("default_threshold", 0.5)),
                config_snapshot=self.config,
            )
        raise ValueError(f"Unsupported artifact type: {artifact_type}")

    def warmup(self, num_runs: int = 10, batch_size: int = 1) -> Dict[str, Any]:
        """Run warmup inference passes to stabilize runtime kernels and caches."""
        if num_runs <= 0:
            return {"num_runs": 0, "status": "skipped"}

        input_size = int(self.config.get("input_size", 224))
        dummy = torch.randn(batch_size, 3, input_size, input_size, dtype=torch.float32, device=self.device)

        with torch.no_grad():
            for _ in range(int(num_runs)):
                _ = self._forward_logits(dummy)

        self.logger.info("Warmup completed | runs=%d batch_size=%d", num_runs, batch_size)
        return {
            "num_runs": int(num_runs),
            "batch_size": int(batch_size),
            "status": "ok",
        }

    def benchmark(
        self,
        batch_size: int = 16,
        num_batches: int = 30,
        warmup_runs: int = 10,
        output_path: Optional[str | Path] = None,
        preprocessor: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Benchmark model latency and throughput with optional preprocessing latency split."""
        if batch_size <= 0 or num_batches <= 0:
            raise ValueError("batch_size and num_batches must be > 0")

        self.warmup(num_runs=warmup_runs, batch_size=batch_size)

        input_size = int(self.config.get("input_size", 224))
        preprocess_latencies: List[float] = []
        model_latencies: List[float] = []

        for _ in range(int(num_batches)):
            if preprocessor is not None:
                random_images = [
                    np.random.randint(0, 256, size=(input_size, input_size, 3), dtype=np.uint8)
                    for _ in range(int(batch_size))
                ]
                start_pre = time.perf_counter()
                tensors = [
                    preprocessor.preprocess_numpy_image(image=img, assume_bgr=False, input_id="benchmark").tensor
                    for img in random_images
                ]
                preprocess_ms = (time.perf_counter() - start_pre) * 1000.0
                preprocess_latencies.append(preprocess_ms)
                batch_tensor = torch.stack(tensors, dim=0)
            else:
                batch_tensor = torch.randn(batch_size, 3, input_size, input_size, dtype=torch.float32)

            start_model = time.perf_counter()
            _ = self.predict_batch(batch_tensor=batch_tensor, threshold=self.default_threshold)
            model_ms = (time.perf_counter() - start_model) * 1000.0
            model_latencies.append(model_ms)

        model_stats = summarize_latencies(model_latencies)
        preprocess_stats = summarize_latencies(preprocess_latencies)

        throughput = 0.0
        if model_stats.total_ms > 0.0:
            throughput = float((batch_size * num_batches) / (model_stats.total_ms / 1000.0))

        summary = {
            "artifact_type": self.artifact_type,
            "artifact_path": str(self.artifact_path.as_posix()),
            "model_name": self.model_name,
            "batch_size": int(batch_size),
            "num_batches": int(num_batches),
            "warmup_runs": int(warmup_runs),
            "avg_model_latency_ms_per_batch": model_stats.avg_ms,
            "min_model_latency_ms_per_batch": model_stats.min_ms,
            "max_model_latency_ms_per_batch": model_stats.max_ms,
            "avg_model_latency_ms_per_sample": model_stats.avg_ms / max(batch_size, 1),
            "throughput_samples_per_sec": throughput,
            "avg_preprocessing_latency_ms_per_batch": preprocess_stats.avg_ms,
            "measured_with_preprocessor": preprocessor is not None,
        }

        if output_path is not None:
            save_serializable_json(summary, output_path)

        self.logger.info(
            "Benchmark complete | avg_batch_ms=%.2f throughput=%.2f samples/sec",
            summary["avg_model_latency_ms_per_batch"],
            summary["throughput_samples_per_sec"],
        )

        return summary

    def predict_tensor(
        self,
        tensor: torch.Tensor,
        threshold: Optional[float] = None,
        input_id: str = "tensor_input",
    ) -> Dict[str, Any]:
        """Run inference for one CHW tensor and return deployment-ready result schema."""
        if tensor.ndim != 3:
            return self._error_result(
                input_id=input_id,
                error_message=f"Expected tensor with shape [C,H,W], got {tuple(tensor.shape)}",
            )

        batch_result = self.predict_batch(
            batch_tensor=tensor.unsqueeze(0),
            threshold=threshold,
            input_ids=[input_id],
        )
        return batch_result[0]

    def predict_batch(
        self,
        batch_tensor: torch.Tensor,
        threshold: Optional[float] = None,
        input_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Run batch inference for BCHW tensor input and return per-sample schema records."""
        if batch_tensor.ndim != 4:
            message = f"Expected batch tensor with shape [B,C,H,W], got {tuple(batch_tensor.shape)}"
            if input_ids is None:
                return [self._error_result(input_id="batch_input", error_message=message)]
            return [self._error_result(input_id=str(input_id), error_message=message) for input_id in input_ids]

        batch_size = int(batch_tensor.shape[0])
        threshold_value = float(self.threshold_from_artifact if threshold is None else threshold)

        if input_ids is None:
            input_ids = [f"sample_{idx}" for idx in range(batch_size)]

        if len(input_ids) != batch_size:
            raise ValueError("Length of input_ids must match batch size")

        start_time = time.perf_counter()
        try:
            logits_tensor = self._forward_logits(batch_tensor)
            logits_np = logits_tensor.detach().cpu().view(-1).numpy().astype(np.float64)
            probs_np = np.asarray(to_probability_from_logit(logits_np), dtype=np.float64)
        except Exception as exc:
            return [self._error_result(input_id=str(sample_id), error_message=f"Inference failed: {exc}") for sample_id in input_ids]

        total_ms = (time.perf_counter() - start_time) * 1000.0
        per_sample_ms = total_ms / max(batch_size, 1)

        results: List[Dict[str, Any]] = []
        for idx in range(batch_size):
            predicted_index = int(probs_np[idx] >= threshold_value)
            predicted_label = class_index_to_name(predicted_index, self.class_names)
            result = {
                "input_id": str(input_ids[idx]),
                "input_path": str(input_ids[idx]) if Path(str(input_ids[idx])).suffix else "",
                "predicted_label": predicted_label,
                "predicted_label_index": predicted_index,
                "predicted_probability": float(probs_np[idx]),
                "predicted_logit": float(logits_np[idx]),
                "threshold_used": threshold_value,
                "model_name": self.model_name,
                "checkpoint_path": self.checkpoint_path,
                "inference_time_ms": float(per_sample_ms),
                "status": "ok",
                "error_message": "",
            }
            results.append(result)

        return results

    def predict_image_path(
        self,
        image_path: str | Path,
        preprocessor: Any,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run end-to-end prediction for a disk image path."""
        preprocess_result = preprocessor.preprocess_image_path(image_path)
        if preprocess_result.status != "ok" or preprocess_result.tensor is None:
            return self._error_result(input_id=str(Path(image_path).as_posix()), error_message=preprocess_result.error_message)

        return self.predict_tensor(
            tensor=preprocess_result.tensor,
            threshold=threshold,
            input_id=str(Path(image_path).as_posix()),
        )

    def predict_numpy_image(
        self,
        image: np.ndarray,
        preprocessor: Any,
        threshold: Optional[float] = None,
        input_id: str = "numpy_input",
        assume_bgr: bool = True,
    ) -> Dict[str, Any]:
        """Run end-to-end prediction for an in-memory numpy image."""
        preprocess_result = preprocessor.preprocess_numpy_image(
            image=image,
            assume_bgr=assume_bgr,
            input_id=input_id,
        )

        if preprocess_result.status != "ok" or preprocess_result.tensor is None:
            return self._error_result(input_id=input_id, error_message=preprocess_result.error_message)

        return self.predict_tensor(
            tensor=preprocess_result.tensor,
            threshold=threshold,
            input_id=input_id,
        )

    def _forward_logits(self, batch_tensor: torch.Tensor) -> torch.Tensor:
        """Forward pass across artifact types with optional AMP support."""
        model_input = batch_tensor.to(self.device, dtype=torch.float32, non_blocking=False)

        sync_device_if_needed(self.device)

        if self.artifact_type in {"pytorch", "torchscript"}:
            autocast_enabled = bool(self.use_amp and self.device.type == "cuda")
            autocast_ctx = (
                torch.amp.autocast(device_type="cuda", enabled=True)
                if autocast_enabled
                else nullcontext()
            )
            with torch.no_grad():
                with autocast_ctx:
                    logits = self.model(model_input)
        elif self.artifact_type == "onnx":
            with torch.no_grad():
                logits = self.model(model_input)
        else:
            raise RuntimeError(f"Unsupported artifact type for forward pass: {self.artifact_type}")

        sync_device_if_needed(self.device)

        if not torch.is_tensor(logits):
            raise RuntimeError("Model forward output is not a tensor")

        return logits.view(-1)

    def _error_result(self, input_id: str, error_message: str) -> Dict[str, Any]:
        """Create standardized error payload for deployment-safe contracts."""
        return {
            "input_id": str(input_id),
            "input_path": str(input_id) if Path(str(input_id)).suffix else "",
            "predicted_label": "",
            "predicted_label_index": -1,
            "predicted_probability": 0.0,
            "predicted_logit": 0.0,
            "threshold_used": float(self.default_threshold),
            "model_name": self.model_name if hasattr(self, "model_name") else "",
            "checkpoint_path": self.checkpoint_path if hasattr(self, "checkpoint_path") else "",
            "inference_time_ms": 0.0,
            "status": "error",
            "error_message": str(error_message),
        }
