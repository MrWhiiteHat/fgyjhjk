"""Video prediction endpoint tests with deterministic stubs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.dependencies import (
    get_file_service,
    get_inference_service,
    get_model_service,
    get_report_service,
    secure_endpoint,
)
from app.backend.main import create_app


@dataclass
class DummySavedUpload:
    original_filename: str
    safe_filename: str
    saved_path: Path
    size_bytes: int
    content_type: str
    sha256: str


class DummyFileService:
    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir

    async def save_video_upload(self, upload):
        data = await upload.read()
        target = self.temp_dir / "sample.mp4"
        target.write_bytes(data)
        return DummySavedUpload(
            original_filename=upload.filename or "sample.mp4",
            safe_filename="sample.mp4",
            saved_path=target,
            size_bytes=len(data),
            content_type=upload.content_type or "video/mp4",
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def cleanup_saved_file(self, _path):
        return None


class DummyInferenceService:
    def predict_video_file(self, **_kwargs):
        return {
            "result": {
                "predicted_label": "REAL",
                "predicted_probability": 0.18,
                "predicted_logit": -1.5,
                "threshold_used": 0.5,
                "inference_time_ms": 88.0,
                "model_name": "dummy-model",
                "checkpoint_path": "dummy.pt",
                "status": "ok",
            },
            "num_frames_processed": 24,
            "fake_frame_ratio": 0.125,
            "aggregation_strategy": "mean_probability",
            "aggregated_probability": 0.18,
            "aggregated_label": "REAL",
            "frame_report_path": "outputs/frame_report.csv",
            "summary": {"ok": True},
        }

    def build_prediction_response(self, raw_result, explanation_available: bool, report_id=None):
        return {
            "predicted_label": raw_result["predicted_label"],
            "predicted_probability": raw_result["predicted_probability"],
            "predicted_logit": raw_result["predicted_logit"],
            "threshold_used": raw_result["threshold_used"],
            "inference_time_ms": raw_result["inference_time_ms"],
            "model_name": raw_result["model_name"],
            "artifact_path": raw_result["checkpoint_path"],
            "confidence_score": 0.82,
            "authenticity_score": 0.18,
            "risk_score": 0.82,
            "risk_level": "high",
            "uncertain_prediction": False,
            "uncertainty_margin": 0.32,
            "final_decision": raw_result["predicted_label"],
            "explanation_available": explanation_available,
            "report_id": report_id,
        }


class DummyReportService:
    def create_report(self, **_kwargs):
        return {"report_id": "video-report-1", "files": {}}


class DummyModelService:
    def get_model_info(self):
        return {
            "model_name": "dummy-model",
            "artifact_path": "dummy.pt",
            "threshold": 0.5,
            "loaded_at": "",
            "device": "cpu",
            "explainability_enabled": True,
            "model_type": "pytorch",
        }


def test_predict_video_endpoint_success(tmp_path: Path) -> None:
    app = create_app()

    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_file_service] = lambda: DummyFileService(tmp_path)
    app.dependency_overrides[get_inference_service] = lambda: DummyInferenceService()
    app.dependency_overrides[get_report_service] = lambda: DummyReportService()
    app.dependency_overrides[get_model_service] = lambda: DummyModelService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predict/video",
            files={"file": ("sample.mp4", b"video-bytes", "video/mp4")},
            data={
                "threshold": "0.5",
                "frame_stride": "1",
                "max_frames": "30",
                "aggregation_strategy": "mean_probability",
                "generate_report": "true",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["result"]["predicted_label"] == "REAL"
    assert payload["data"]["num_frames_processed"] == 24
