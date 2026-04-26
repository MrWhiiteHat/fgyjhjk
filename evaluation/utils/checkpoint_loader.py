"""Model artifact resolution and loading utilities for evaluation and inference."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import torch

from evaluation.utils.helpers import load_yaml, safe_div


@dataclass
class ArtifactBundle:
    """Container describing a loaded model artifact and metadata."""

    model: Any
    artifact_type: str
    artifact_path: Path
    model_name: str
    checkpoint_path: str
    threshold: float
    config_snapshot: Dict[str, Any]


class OnnxBinaryClassifierWrapper:
    """ONNX Runtime wrapper exposing a torch-like callable interface."""

    def __init__(self, session: Any, input_name: str, output_name: str) -> None:
        self.session = session
        self.input_name = input_name
        self.output_name = output_name

    def __call__(self, batch_tensor: torch.Tensor) -> torch.Tensor:
        """Run ONNX forward pass and return tensor logits on CPU."""
        if batch_tensor.ndim != 4:
            raise ValueError(f"Expected 4D input tensor for ONNX runtime, got shape={tuple(batch_tensor.shape)}")
        input_array = batch_tensor.detach().cpu().numpy().astype("float32")
        outputs = self.session.run([self.output_name], {self.input_name: input_array})
        logits = outputs[0]
        return torch.from_numpy(logits).view(-1)


def _load_possible_config_snapshot_from_checkpoint_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Try reading embedded config-like dictionaries from checkpoint payload."""
    config_candidates = ["config", "config_snapshot", "train_config", "cfg"]
    for key in config_candidates:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _resolve_report_config_snapshot(checkpoint_path: Path) -> Dict[str, Any]:
    """Try resolving a config snapshot from nearby report directories."""
    parts = list(checkpoint_path.parts)
    if "checkpoints" in parts:
        idx = parts.index("checkpoints")
        if idx + 1 < len(parts):
            experiment_name = parts[idx + 1]
            base_parts = parts[:idx]
            report_candidate = Path(*base_parts) / "reports" / experiment_name / "config_snapshot.yaml"
            if report_candidate.exists() and report_candidate.is_file():
                try:
                    return load_yaml(report_candidate)
                except Exception:
                    return {}

    same_dir_candidate = checkpoint_path.parent / "config_snapshot.yaml"
    if same_dir_candidate.exists() and same_dir_candidate.is_file():
        try:
            return load_yaml(same_dir_candidate)
        except Exception:
            return {}

    return {}


def _resolve_threshold_from_report(checkpoint_path: Path) -> Optional[float]:
    """Read threshold from final report if available."""
    parts = list(checkpoint_path.parts)
    if "checkpoints" not in parts:
        return None

    idx = parts.index("checkpoints")
    if idx + 1 >= len(parts):
        return None

    experiment_name = parts[idx + 1]
    base_parts = parts[:idx]
    report_json = Path(*base_parts) / "reports" / experiment_name / "final_experiment_report.json"
    if not report_json.exists() or not report_json.is_file():
        return None

    try:
        with report_json.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if "threshold_used" in payload:
            return float(payload["threshold_used"])
    except Exception:
        return None

    return None


def _extract_state_dict(payload: Dict[str, Any], checkpoint_path: Path) -> Dict[str, Any]:
    """Extract a model state_dict from diverse checkpoint formats."""
    if "model_state_dict" in payload and isinstance(payload["model_state_dict"], dict):
        return payload["model_state_dict"]
    if "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]

    if all(isinstance(k, str) for k in payload.keys()) and any(torch.is_tensor(v) for v in payload.values()):
        return payload

    raise KeyError(
        "Missing state dict in checkpoint. Expected keys 'model_state_dict' or 'state_dict'. "
        f"Checkpoint: {checkpoint_path}"
    )


def resolve_model_artifact(config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Resolve which artifact should be loaded based on config flags."""
    checkpoint_path = Path(str(config.get("checkpoint_path", "")).strip())
    exported_model_path = Path(str(config.get("exported_model_path", "")).strip())
    use_torchscript = bool(config.get("use_torchscript", False))
    use_onnx = bool(config.get("use_onnx", False))

    if use_torchscript and use_onnx:
        raise ValueError("Config is invalid: use_torchscript and use_onnx cannot both be true")

    if use_onnx:
        artifact_path = exported_model_path
        artifact_type = "onnx"
    elif use_torchscript:
        artifact_path = exported_model_path
        artifact_type = "torchscript"
    else:
        artifact_path = checkpoint_path
        artifact_type = "pytorch"

    if not str(artifact_path):
        raise ValueError("No artifact path resolved from config")

    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileNotFoundError(f"Resolved model artifact does not exist: {artifact_path}")

    logger.info("Resolved artifact type=%s path=%s", artifact_type, artifact_path)
    return {
        "artifact_type": artifact_type,
        "artifact_path": artifact_path,
        "checkpoint_path": checkpoint_path,
    }


def load_pytorch_model(
    model_config: Dict[str, Any],
    checkpoint_path: str | Path,
    device: torch.device,
    logger: logging.Logger,
    strict: bool = True,
) -> ArtifactBundle:
    """Load PyTorch checkpoint by restoring architecture and weight state."""
    ckpt_path = Path(checkpoint_path)
    if not ckpt_path.exists() or not ckpt_path.is_file():
        raise FileNotFoundError(f"Checkpoint file does not exist: {ckpt_path}")

    try:
        payload = torch.load(ckpt_path, map_location=device)
    except Exception as exc:
        raise RuntimeError(f"Checkpoint appears corrupt or unreadable: {ckpt_path} | {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Checkpoint payload must be a dictionary: {ckpt_path}")

    embedded_config = _load_possible_config_snapshot_from_checkpoint_payload(payload)
    snapshot_config = _resolve_report_config_snapshot(ckpt_path)

    merged_config: Dict[str, Any] = {}
    merged_config.update(snapshot_config)
    merged_config.update(embedded_config)
    merged_config.update(model_config)

    required_keys = ["backbone", "pretrained", "freeze_backbone", "dropout", "hidden_dim"]
    missing_for_arch = [key for key in required_keys if key not in merged_config]
    if missing_for_arch:
        raise KeyError(
            "Unable to restore model architecture from config. "
            f"Missing keys: {missing_for_arch}. "
            "Provide these values in evaluation config or ensure training config snapshot is available."
        )

    try:
        from training.models.model_factory import create_model

        model = create_model(merged_config, logger).to(device)
    except Exception as exc:
        raise RuntimeError(f"Failed to instantiate model architecture: {exc}") from exc

    state_dict = _extract_state_dict(payload, ckpt_path)

    try:
        model.load_state_dict(state_dict, strict=bool(strict))
    except RuntimeError as exc:
        message = str(exc)
        if "size mismatch" in message.lower() and "classifier" in message.lower():
            raise RuntimeError(
                "Classifier head shape mismatch while loading checkpoint. "
                "Check backbone/hidden_dim/dropout settings against training config."
            ) from exc
        if not strict:
            logger.warning("Non-strict checkpoint load reported mismatch: %s", message)
        else:
            raise RuntimeError(f"Checkpoint architecture is incompatible: {message}") from exc

    model.eval()

    threshold = payload.get("threshold")
    if threshold is None:
        threshold = payload.get("best_threshold")
    if threshold is None:
        threshold = _resolve_threshold_from_report(ckpt_path)
    if threshold is None:
        threshold = model_config.get("default_threshold", 0.5)

    model_name = str(merged_config.get("backbone", "unknown_backbone"))

    logger.info("Loaded PyTorch model from %s", ckpt_path)
    logger.info("Resolved threshold: %.6f", float(threshold))

    return ArtifactBundle(
        model=model,
        artifact_type="pytorch",
        artifact_path=ckpt_path,
        model_name=model_name,
        checkpoint_path=str(ckpt_path.as_posix()),
        threshold=float(threshold),
        config_snapshot=merged_config,
    )


def load_torchscript_model(
    torchscript_path: str | Path,
    device: torch.device,
    logger: logging.Logger,
    default_threshold: float = 0.5,
    config_snapshot: Optional[Dict[str, Any]] = None,
) -> ArtifactBundle:
    """Load TorchScript artifact for production-friendly inference."""
    ts_path = Path(torchscript_path)
    if not ts_path.exists() or not ts_path.is_file():
        raise FileNotFoundError(f"TorchScript file does not exist: {ts_path}")

    try:
        model = torch.jit.load(str(ts_path), map_location=device)
    except Exception as exc:
        raise RuntimeError(f"TorchScript model is corrupt or incompatible: {ts_path} | {exc}") from exc

    model.eval()
    logger.info("Loaded TorchScript model from %s", ts_path)

    snapshot = config_snapshot or {}
    model_name = str(snapshot.get("backbone", "torchscript_model"))

    return ArtifactBundle(
        model=model,
        artifact_type="torchscript",
        artifact_path=ts_path,
        model_name=model_name,
        checkpoint_path="",
        threshold=float(default_threshold),
        config_snapshot=snapshot,
    )


def load_onnx_model(
    onnx_path: str | Path,
    device: torch.device,
    logger: logging.Logger,
    default_threshold: float = 0.5,
    config_snapshot: Optional[Dict[str, Any]] = None,
) -> ArtifactBundle:
    """Load ONNX model with onnxruntime and wrap it in a callable interface."""
    model_path = Path(onnx_path)
    if not model_path.exists() or not model_path.is_file():
        raise FileNotFoundError(f"ONNX file does not exist: {model_path}")

    try:
        import onnxruntime as ort
    except Exception as exc:
        raise ImportError(
            "onnxruntime is required for ONNX inference. Install it with: pip install onnxruntime"
        ) from exc

    available_providers = ort.get_available_providers()
    providers = ["CPUExecutionProvider"]
    if device.type == "cuda" and "CUDAExecutionProvider" in available_providers:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    try:
        session = ort.InferenceSession(str(model_path), providers=providers)
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize ONNX runtime session: {model_path} | {exc}") from exc

    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if not inputs:
        raise RuntimeError(f"ONNX model has no inputs: {model_path}")
    if not outputs:
        raise RuntimeError(f"ONNX model has no outputs: {model_path}")

    wrapper = OnnxBinaryClassifierWrapper(session=session, input_name=inputs[0].name, output_name=outputs[0].name)
    logger.info("Loaded ONNX model from %s using providers=%s", model_path, providers)

    snapshot = config_snapshot or {}
    model_name = str(snapshot.get("backbone", "onnx_model"))

    return ArtifactBundle(
        model=wrapper,
        artifact_type="onnx",
        artifact_path=model_path,
        model_name=model_name,
        checkpoint_path="",
        threshold=float(default_threshold),
        config_snapshot=snapshot,
    )


def verify_model_forward_pass(
    model: Any,
    input_size: int,
    device: torch.device,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Run a dummy forward pass and validate output tensor shape and finiteness."""
    dummy = torch.randn(1, 3, int(input_size), int(input_size), device=device, dtype=torch.float32)

    try:
        with torch.no_grad():
            output = model(dummy)
    except Exception as exc:
        raise RuntimeError(f"Model forward pass failed on dummy input: {exc}") from exc

    if not torch.is_tensor(output):
        raise RuntimeError("Model forward pass did not return a torch.Tensor")

    output_flat = output.detach().view(-1)
    if output_flat.numel() < 1:
        raise RuntimeError("Model forward pass returned empty output tensor")

    finite_ratio = float(torch.isfinite(output_flat).float().mean().item())
    if finite_ratio < 1.0:
        raise RuntimeError("Model forward pass returned NaN/Inf values")

    summary = {
        "ok": True,
        "output_shape": tuple(output.shape),
        "num_outputs": int(output_flat.numel()),
        "finite_ratio": finite_ratio,
        "sample_logit": float(output_flat[0].item()),
    }

    logger.info(
        "Forward pass verified | output_shape=%s finite_ratio=%.2f",
        summary["output_shape"],
        summary["finite_ratio"],
    )

    return summary
