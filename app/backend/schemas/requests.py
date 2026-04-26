"""Pydantic request schemas for API endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ImagePredictionRequest(BaseModel):
    """Request options for image prediction endpoint."""

    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    explain: bool = False
    generate_report: bool = True


class FolderPredictionRequest(BaseModel):
    """Request options for folder/archive prediction endpoint."""

    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recursive: bool = True
    generate_report: bool = True


class VideoPredictionRequest(BaseModel):
    """Request options for video prediction endpoint."""

    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frame_stride: int = Field(default=1, ge=1)
    max_frames: int = Field(default=0, ge=0)
    aggregation_strategy: Literal[
        "mean_probability",
        "max_probability",
        "fake_frame_ratio",
        "majority_vote",
        "sliding_window_mean",
        "sliding_window_max",
    ] = "mean_probability"
    generate_report: bool = True


class ExplainabilityRequest(BaseModel):
    """Request options for explainability endpoint."""

    explanation_type: Literal["gradcam", "saliency", "both"] = "both"
    target_layer: Optional[str] = None


class ReportQueryRequest(BaseModel):
    """Request options for report lookup endpoint."""

    report_format: Literal["json", "txt", "csv"] = "json"


class GenerateReportRequest(BaseModel):
    """Request payload for explicit report generation route."""

    request_metadata: dict = Field(default_factory=dict)
    file_metadata: dict = Field(default_factory=dict)
    prediction_results: dict = Field(default_factory=dict)
    explanation_outputs: dict | None = None
    model_metadata: dict | None = None


class AdminReloadRequest(BaseModel):
    """Request payload for admin model reload endpoint."""

    force: bool = False
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
