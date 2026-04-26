"""Pydantic response schemas for backend API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.backend.schemas.common import BaseResponse


class PredictionResult(BaseModel):
    """Core prediction result contract shared across modes."""

    predicted_label: str
    predicted_probability: float
    predicted_logit: float
    threshold_used: float
    inference_time_ms: float
    model_name: str
    artifact_path: str
    confidence_score: float
    authenticity_score: float
    risk_score: float
    risk_level: str
    uncertain_prediction: bool
    uncertainty_margin: float
    final_decision: str
    explanation_available: bool
    report_id: Optional[str] = None


class HealthData(BaseModel):
    """Health endpoint payload."""

    app_status: str
    model_loaded: bool
    artifact_path: str
    device: str
    uptime_seconds: float
    version: str


class ReadyData(BaseModel):
    """Readiness endpoint payload."""

    ready: bool
    app_status: str
    model_loaded: bool
    artifact_path: str
    artifact_exists: bool
    last_load_error: str
    version: str


class ImagePredictionData(BaseModel):
    """Image prediction payload."""

    prediction: PredictionResult
    timing: Dict[str, float] = {}
    cache_hit: bool = False
    metadata_summary: Dict[str, Any] = {}
    explainability: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None


class FolderPredictionData(BaseModel):
    """Folder prediction payload."""

    results: List[PredictionResult]
    summary: Dict[str, Any]
    report_id: Optional[str] = None


class VideoPredictionData(BaseModel):
    """Video prediction payload."""

    result: PredictionResult
    num_frames_processed: int
    fake_frame_ratio: float
    aggregation_strategy: str
    aggregated_probability: float
    aggregated_label: str
    frame_report_path: str
    cache_hit: bool = False
    metadata_summary: Dict[str, Any] = {}


class ExplainabilityData(BaseModel):
    """Explainability endpoint payload."""

    explanation_type: str
    target_layer: str
    heatmap_path: str
    overlay_path: str
    generated_at: str


class ReportData(BaseModel):
    """Report retrieval payload."""

    report_id: str
    metadata: Dict[str, Any]
    files: Dict[str, str]


class ModelInfoData(BaseModel):
    """Admin model metadata payload."""

    model_name: str
    artifact_path: str
    threshold: float
    loaded_at: str
    device: str
    explainability_enabled: bool
    model_type: str


class HealthResponse(BaseResponse):
    data: HealthData


class ReadyResponse(BaseResponse):
    data: ReadyData


class ImagePredictionResponse(BaseResponse):
    data: ImagePredictionData


class FolderPredictionResponse(BaseResponse):
    data: FolderPredictionData


class VideoPredictionResponse(BaseResponse):
    data: VideoPredictionData


class ExplainabilityResponse(BaseResponse):
    data: ExplainabilityData


class ReportResponse(BaseResponse):
    data: ReportData


class ModelInfoResponse(BaseResponse):
    data: ModelInfoData
