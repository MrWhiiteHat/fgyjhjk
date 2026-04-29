"""Image prediction endpoint tests with service stubs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.core.exceptions import ExplainabilityError
from app.backend.dependencies import (
    get_explainability_service,
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

    async def save_image_upload(self, upload):
        data = await upload.read()
        target = self.temp_dir / "test_image.jpg"
        target.write_bytes(data)
        return DummySavedUpload(
            original_filename=upload.filename or "test_image.jpg",
            safe_filename="test_image.jpg",
            saved_path=target,
            size_bytes=len(data),
            content_type=upload.content_type or "image/jpeg",
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def cleanup_saved_file(self, _path):
        return None


class DummyInferenceService:
    def predict_image_with_timeout(self, image_path: str, threshold: float | None = None, file_digest: str | None = None):
        _ = image_path
        _ = file_digest
        return {
            "result": {
                "predicted_label": "FAKE",
                "predicted_probability": 0.91,
                "predicted_logit": 2.3,
                "threshold_used": 0.6 if threshold is not None else 0.5,
                "inference_time_ms": 12.0,
                "model_name": "dummy-model",
                "checkpoint_path": "dummy.pt",
                "status": "ok",
            },
            "timing": {
                "preprocessing_time_ms": 2.0,
                "model_time_ms": 10.0,
                "end_to_end_time_ms": 12.0,
            },
            "cache_hit": False,
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
            "confidence_score": 0.91,
            "authenticity_score": 0.09,
            "risk_score": 0.91,
            "risk_level": "high",
            "uncertain_prediction": False,
            "uncertainty_margin": 0.31,
            "final_decision": raw_result["predicted_label"],
            "explanation_available": explanation_available,
            "report_id": report_id,
        }

class DummyExplainabilityService:
    def explain_image(self, image_path: str, explanation_type: str = "both", target_layer: str | None = None, **kwargs):
        _ = (image_path, explanation_type, target_layer, kwargs)
        return {
            "explanation_type": "both",
            "target_layer": "layer4",
            "heatmap_path": "outputs/heatmap.png",
            "overlay_path": "outputs/overlay.png",
            "generated_at": "2026-01-01T00:00:00Z",
        }


class DummyReportService:
    def create_report(self, **_kwargs):
        return {
            "report_id": "report-123",
            "files": {
                "json": "outputs/reports/report-123/report.json",
                "txt": "outputs/reports/report-123/report.txt",
                "csv": "outputs/reports/report-123/prediction_rows.csv",
            },
        }


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


class FailingExplainabilityService:
    def explain_image(self, image_path: str, explanation_type: str = "both", target_layer: str | None = None, **kwargs):
        _ = (image_path, explanation_type, target_layer, kwargs)
        raise ExplainabilityError("Explainability failed for sample")


def test_predict_image_endpoint_success(tmp_path: Path) -> None:
    app = create_app()

    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_file_service] = lambda: DummyFileService(tmp_path)
    app.dependency_overrides[get_inference_service] = lambda: DummyInferenceService()
    app.dependency_overrides[get_explainability_service] = lambda: DummyExplainabilityService()
    app.dependency_overrides[get_report_service] = lambda: DummyReportService()
    app.dependency_overrides[get_model_service] = lambda: DummyModelService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predict/image",
            files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"threshold": "0.6", "explain": "true", "generate_report": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["prediction"]["predicted_label"] == "FAKE"
    assert payload["data"]["prediction"]["report_id"] == "report-123"
    assert payload["data"]["explainability"]["heatmap_path"].endswith("heatmap.png")


def test_predict_image_succeeds_when_explainability_fails(tmp_path: Path) -> None:
    app = create_app()

    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_file_service] = lambda: DummyFileService(tmp_path)
    app.dependency_overrides[get_inference_service] = lambda: DummyInferenceService()
    app.dependency_overrides[get_explainability_service] = lambda: FailingExplainabilityService()
    app.dependency_overrides[get_report_service] = lambda: DummyReportService()
    app.dependency_overrides[get_model_service] = lambda: DummyModelService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predict/image",
            files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"threshold": "0.6", "explain": "true", "generate_report": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["prediction"]["predicted_label"] == "FAKE"
    assert payload["data"]["prediction"]["report_id"] == "report-123"
    assert payload["data"]["explainability"] is None
    assert payload["message"] == "Image prediction completed with warnings"
    assert any(
        "Explainability unavailable" in warning
        for warning in payload["data"]["metadata_summary"].get("warnings", [])
    )
