"""Health endpoint tests for API readiness contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.dependencies import get_model_service, secure_endpoint
from app.backend.main import create_app


class DummyModelService:
    def get_model_info(self):
        return {
            "loaded": True,
            "artifact_path": "training/outputs/checkpoints/real_fake_baseline/best_model.pt",
            "device": "cpu",
        }


def test_health_endpoint_returns_ok_payload() -> None:
    app = create_app()
    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_model_service] = lambda: DummyModelService()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["app_status"] == "ok"
    assert payload["data"]["model_loaded"] is True
    assert payload["data"]["artifact_path"].endswith("best_model.pt")
