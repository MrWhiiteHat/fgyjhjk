"""Thread-safe singleton model manager integrating Module 4 predictor utilities."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from app.backend.config import get_settings
from app.backend.core.runtime_compat import apply_windows_torch_platform_patch
from app.backend.core.exceptions import ModelNotLoadedError
from app.backend.utils.logger import configure_logger


class ModelService:
    """Singleton model manager with lazy loading and reload support."""

    _instance: "ModelService | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = configure_logger("backend.model_service", self.settings.LOG_LEVEL, f"{self.settings.OUTPUT_DIR}/logs")
        self._lock = threading.RLock()
        self._predictor = None
        self._preprocessor = None
        self._loaded_at: str = ""
        self._model_version: int = 0
        self._last_load_error: str = ""

    @classmethod
    def get_instance(cls) -> "ModelService":
        """Get global singleton model service instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = ModelService()
        return cls._instance

    @property
    def model_version(self) -> str:
        """Return model version token used for cache keys."""
        return str(self._model_version)

    def _load_eval_base_config(self) -> Dict[str, Any]:
        """Load base evaluation config from Module 4 config file when present."""
        eval_cfg_path = Path("evaluation/configs/eval_config.yaml")
        if eval_cfg_path.exists() and eval_cfg_path.is_file():
            with eval_cfg_path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
            if isinstance(payload, dict):
                return payload
        return {}

    def _build_runtime_eval_config(self) -> Dict[str, Any]:
        """Build effective runtime config for predictor and preprocessing."""
        cfg = self._load_eval_base_config()

        cfg["checkpoint_path"] = self.settings.MODEL_ARTIFACT_PATH
        cfg["default_threshold"] = float(self.settings.DEFAULT_THRESHOLD)
        cfg["device"] = self.settings.DEVICE
        cfg["output_dir"] = str((Path(self.settings.OUTPUT_DIR) / "evaluation_bridge").as_posix())
        cfg["enable_explainability"] = bool(self.settings.ENABLE_EXPLAINABILITY)
        cfg["explain_max_image_side"] = int(self.settings.EXPLAIN_MAX_IMAGE_SIDE)
        cfg["save_explainability_panels"] = bool(self.settings.SAVE_EXPLAINABILITY_PANELS)

        model_type = str(self.settings.MODEL_TYPE).strip().lower()
        cfg["use_torchscript"] = model_type == "torchscript"
        cfg["use_onnx"] = model_type == "onnx"
        if model_type in {"torchscript", "onnx"}:
            cfg["exported_model_path"] = self.settings.MODEL_ARTIFACT_PATH

        return cfg

    def load_model(self, strict_checkpoint_loading: bool = True) -> None:
        """Load predictor and preprocessor instances with synchronized access."""
        # Import OUTSIDE the lock — these can take 5-15s on first call due to
        # transitive imports of torch, timm, cv2, etc.
        self.logger.info("LOAD_IMPORT_START | Importing Predictor and InferencePreprocessor classes")
        try:
            from evaluation.inference.predictor import Predictor
            from evaluation.inference.preprocessing_adapter import InferencePreprocessor
        except Exception as exc:
            self._last_load_error = f"Module import failed: {exc}"
            self.logger.exception("LOAD_IMPORT_FAILED | %s", self._last_load_error)
            raise ModelNotLoadedError("Failed to import model modules", details={"cause": str(exc)}) from exc
        self.logger.info("LOAD_IMPORT_DONE | Imports completed successfully")

        with self._lock:
            self.logger.info("LOAD_LOCK_ACQUIRED | Building runtime config")
            runtime_cfg = self._build_runtime_eval_config()
            apply_windows_torch_platform_patch(self.logger)
            artifact = Path(str(runtime_cfg.get("checkpoint_path" if self.settings.MODEL_TYPE == "pytorch" else "exported_model_path", "")))
            if not artifact.exists() or not artifact.is_file():
                self._last_load_error = f"Model artifact not found: {artifact}"
                self.logger.error("LOAD_ARTIFACT_MISSING | %s", self._last_load_error)
                raise ModelNotLoadedError(self._last_load_error)

            self.logger.info("LOAD_ARTIFACT_CHECK | path=%s size_mb=%.1f", artifact, artifact.stat().st_size / (1024 * 1024))

            try:
                self.logger.info("LOAD_PREDICTOR_START | strict=%s device=%s", strict_checkpoint_loading, runtime_cfg.get("device"))
                predictor = Predictor(config=runtime_cfg, logger=self.logger, strict_checkpoint_loading=strict_checkpoint_loading)
                self.logger.info("LOAD_PREDICTOR_DONE | model_name=%s", getattr(predictor, "model_name", "unknown"))

                self.logger.info("LOAD_PREPROCESSOR_START")
                preprocessor = InferencePreprocessor(config=runtime_cfg)
                self.logger.info("LOAD_PREPROCESSOR_DONE | input_size=%s", runtime_cfg.get("input_size", 224))
            except Exception as exc:
                self._last_load_error = str(exc)
                self.logger.exception("LOAD_FAILED | %s", self._last_load_error)
                raise ModelNotLoadedError("Failed to load model artifact", details={"cause": str(exc)}) from exc

            self._predictor = predictor
            self._preprocessor = preprocessor
            self._model_version += 1
            self._loaded_at = datetime.now(timezone.utc).isoformat()
            self._last_load_error = ""

            self.logger.info(
                "Model loaded successfully | type=%s artifact=%s version=%s",
                self.settings.MODEL_TYPE,
                self.settings.MODEL_ARTIFACT_PATH,
                self.model_version,
            )

    def get_predictor(self):
        """Get loaded predictor; lazily load when first accessed."""
        with self._lock:
            if self._predictor is None:
                self.logger.info("LAZY_LOAD_TRIGGERED | Predictor not loaded, triggering lazy load")
                self.load_model(strict_checkpoint_loading=True)
            return self._predictor

    def get_model(self):
        """Get underlying model object from predictor."""
        predictor = self.get_predictor()
        return predictor.model

    def get_preprocessor(self):
        """Get deterministic inference preprocessor."""
        with self._lock:
            if self._preprocessor is None:
                self.logger.info("LAZY_LOAD_TRIGGERED | Preprocessor not loaded, triggering lazy load")
                self.load_model(strict_checkpoint_loading=True)
            return self._preprocessor

    def reload_model(self, strict_checkpoint_loading: bool = True, threshold: float | None = None) -> Dict[str, Any]:
        """Reload model artifact safely and return updated metadata."""
        if threshold is not None:
            self.settings.DEFAULT_THRESHOLD = float(threshold)

        with self._lock:
            self._predictor = None
            self._preprocessor = None
        self.load_model(strict_checkpoint_loading=strict_checkpoint_loading)
        return self.get_model_info()

    def get_eval_runtime_config(self) -> Dict[str, Any]:
        """Expose runtime evaluation config snapshot used by services."""
        return self._build_runtime_eval_config()

    def get_model_info(self) -> Dict[str, Any]:
        """Return metadata describing current loaded model state."""
        loaded = self._predictor is not None
        predictor = self._predictor

        return {
            "model_name": str(getattr(predictor, "model_name", "")) if loaded else "",
            "artifact_path": str(self.settings.MODEL_ARTIFACT_PATH),
            "threshold": float(self.settings.DEFAULT_THRESHOLD),
            "device": str(self.settings.DEVICE),
            "model_type": str(self.settings.MODEL_TYPE),
            "loaded": bool(loaded),
            "loaded_at": self._loaded_at,
            "model_version": self.model_version,
            "last_load_error": self._last_load_error,
            "explainability_enabled": bool(self.settings.ENABLE_EXPLAINABILITY),
        }
