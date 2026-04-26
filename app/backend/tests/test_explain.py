"""Explainability endpoint tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.dependencies import get_explainability_service, get_file_service, secure_endpoint
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
        target = self.temp_dir / "explain.jpg"
        target.write_bytes(data)
        return DummySavedUpload(
            original_filename=upload.filename or "explain.jpg",
            safe_filename="explain.jpg",
            saved_path=target,
            size_bytes=len(data),
            content_type=upload.content_type or "image/jpeg",
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def cleanup_saved_file(self, _path):
        return None


class DummyExplainabilityService:
    def explain_image(self, image_path: str, explanation_type: str = "both", target_layer: str | None = None):
        _ = image_path
        return {
            "explanation_type": explanation_type,
            "target_layer": target_layer or "layer4",
            "heatmap_path": "outputs/heatmap.png",
            "overlay_path": "outputs/overlay.png",
            "generated_at": "2026-01-01T00:00:00Z",
        }


def test_explain_endpoint_returns_paths(tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_file_service] = lambda: DummyFileService(tmp_path)
    app.dependency_overrides[get_explainability_service] = lambda: DummyExplainabilityService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/explain/image",
            files={"file": ("face.jpg", b"image-bytes", "image/jpeg")},
            data={"explanation_type": "gradcam", "target_layer": "layer4"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["explanation_type"] == "gradcam"
    assert payload["data"]["overlay_path"].endswith("overlay.png")
