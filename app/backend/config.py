"""Environment-driven configuration with strict validation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file="app/backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "RealFakeDetectionAPI"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    MODEL_ARTIFACT_PATH: str = "app/backend/models/best_model.pt"
    MODEL_TYPE: str = "pytorch"
    DEVICE: str = "auto"
    MODEL_PRELOAD_ON_STARTUP: bool = True
    DEFAULT_THRESHOLD: float = 0.5
    UNCERTAIN_MARGIN: float = 0.08

    MAX_IMAGE_SIZE_MB: float = 10.0
    MAX_VIDEO_SIZE_MB: float = 250.0
    ALLOWED_IMAGE_EXTENSIONS: List[str] = Field(default_factory=lambda: [".jpg", ".jpeg", ".png", ".bmp", ".webp"])
    ALLOWED_VIDEO_EXTENSIONS: List[str] = Field(default_factory=lambda: [".mp4", ".avi", ".mov", ".mkv", ".webm"])

    TEMP_DIR: str = "app/backend/tmp"
    OUTPUT_DIR: str = "app/backend/outputs"
    TEMP_CLEANUP_ENABLED: bool = True
    TEMP_MAX_AGE_SECONDS: int = 3600
    PRESERVE_FAILED_UPLOADS: bool = False

    ENABLE_EXPLAINABILITY: bool = True
    ENABLE_REPORT_EXPORT: bool = True
    ENABLE_CORS: bool = True
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    REQUEST_TIMEOUT_SEC: int = 60
    PREDICTION_CACHE_TTL: int = 300
    MAX_BATCH_SIZE: int = 64
    VIDEO_DEFAULT_FRAME_STRIDE: int = 3
    VIDEO_DEFAULT_MAX_FRAMES: int = 60
    VIDEO_MAX_FRAMES_PER_REQUEST: int = 180
    VIDEO_MAX_FRAME_STRIDE: int = 16
    VIDEO_INFERENCE_BATCH_SIZE: int = 4
    EXPLAIN_MAX_IMAGE_SIDE: int = 1280
    SAVE_EXPLAINABILITY_PANELS: bool = False

    ENABLE_AUTH: bool = False
    API_KEY: str = ""

    ENABLE_RATE_LIMIT: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120

    SAVE_UPLOADS: bool = False
    SAVE_ANNOTATED_OUTPUTS: bool = False
    SAVE_REPORTS: bool = True

    FRONTEND_BASE_URL: str = "http://localhost:3000"
    BACKEND_BASE_URL: str = "http://localhost:8000"

    METRICS_ENABLED: bool = True
    PROMETHEUS_ENABLED: bool = True

    @field_validator("MODEL_TYPE")
    @classmethod
    def validate_model_type(cls, value: str) -> str:
        """Validate supported model artifact type."""
        lowered = str(value).strip().lower()
        supported = {"pytorch", "torchscript", "onnx"}
        if lowered not in supported:
            raise ValueError(f"MODEL_TYPE must be one of {sorted(supported)}")
        return lowered

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        """Validate deployment environment values."""
        lowered = str(value).strip().lower()
        supported = {"development", "staging", "production", "test"}
        if lowered not in supported:
            raise ValueError(f"APP_ENV must be one of {sorted(supported)}")
        return lowered

    @field_validator("DEFAULT_THRESHOLD")
    @classmethod
    def validate_threshold(cls, value: float) -> float:
        """Ensure default threshold stays within probability range."""
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("DEFAULT_THRESHOLD must be in [0.0, 1.0]")
        return float(value)

    @field_validator("UNCERTAIN_MARGIN")
    @classmethod
    def validate_uncertain_margin(cls, value: float) -> float:
        """Ensure uncertainty margin stays in valid probability range."""
        margin = float(value)
        if not 0.0 <= margin <= 0.5:
            raise ValueError("UNCERTAIN_MARGIN must be in [0.0, 0.5]")
        return margin

    @field_validator("MAX_IMAGE_SIZE_MB", "MAX_VIDEO_SIZE_MB")
    @classmethod
    def validate_max_sizes(cls, value: float) -> float:
        """Validate positive file size limits."""
        if float(value) <= 0:
            raise ValueError("File size limits must be > 0")
        return float(value)

    @field_validator(
        "REQUEST_TIMEOUT_SEC",
        "PREDICTION_CACHE_TTL",
        "RATE_LIMIT_PER_MINUTE",
        "MAX_BATCH_SIZE",
        "VIDEO_DEFAULT_FRAME_STRIDE",
        "VIDEO_DEFAULT_MAX_FRAMES",
        "VIDEO_MAX_FRAMES_PER_REQUEST",
        "VIDEO_MAX_FRAME_STRIDE",
        "VIDEO_INFERENCE_BATCH_SIZE",
        "EXPLAIN_MAX_IMAGE_SIDE",
    )
    @classmethod
    def validate_positive_integers(cls, value: int) -> int:
        """Validate positive integer settings."""
        if int(value) <= 0:
            raise ValueError("Value must be > 0")
        return int(value)

    @field_validator("TEMP_MAX_AGE_SECONDS")
    @classmethod
    def validate_temp_max_age(cls, value: int) -> int:
        """Validate non-negative temp cleanup age."""
        if int(value) < 0:
            raise ValueError("TEMP_MAX_AGE_SECONDS must be >= 0")
        return int(value)

    @field_validator("ALLOWED_IMAGE_EXTENSIONS", "ALLOWED_VIDEO_EXTENSIONS", mode="before")
    @classmethod
    def parse_extensions(cls, value: Any) -> List[str]:
        """Parse comma-separated or list extension config into normalized list."""
        if isinstance(value, str):
            items = [part.strip().lower() for part in value.split(",") if part.strip()]
        elif isinstance(value, list):
            items = [str(part).strip().lower() for part in value if str(part).strip()]
        else:
            raise ValueError("Extensions must be provided as list or comma-separated string")

        normalized = []
        for ext in items:
            norm = ext if ext.startswith(".") else f".{ext}"
            normalized.append(norm)

        if not normalized:
            raise ValueError("At least one file extension must be configured")
        return sorted(set(normalized))

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> List[str]:
        """Parse CORS origins from CSV string or list."""
        if isinstance(value, str):
            origins = [part.strip() for part in value.split(",") if part.strip()]
            return origins or ["*"]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()] or ["*"]
        raise ValueError("CORS_ORIGINS must be list or comma-separated string")

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key_when_auth_enabled(cls, value: str, info) -> str:
        """Require API key value when auth is enabled."""
        data = info.data
        auth_enabled = bool(data.get("ENABLE_AUTH", False))
        if auth_enabled and not str(value).strip():
            raise ValueError("API_KEY must be set when ENABLE_AUTH=true")
        return str(value)

    @property
    def temp_dir_path(self) -> Path:
        """Return normalized temporary directory path."""
        return Path(self.TEMP_DIR)

    @property
    def output_dir_path(self) -> Path:
        """Return normalized output directory path."""
        return Path(self.OUTPUT_DIR)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached application settings singleton."""
    return Settings()
