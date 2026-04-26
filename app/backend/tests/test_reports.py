"""Report lookup endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.dependencies import get_report_service, secure_endpoint
from app.backend.main import create_app


class DummyReportService:
    def get_report(self, report_id: str):
        return {
            "report_id": report_id,
            "metadata": {
                "created_at": "2026-01-01T00:00:00Z",
                "request_id": "req-1",
                "json_path": "outputs/reports/req-1/report.json",
            },
            "files": {
                "json": "outputs/reports/req-1/report.json",
                "txt": "outputs/reports/req-1/report.txt",
                "csv": "outputs/reports/req-1/prediction_rows.csv",
            },
        }


def test_report_lookup_success() -> None:
    app = create_app()
    app.dependency_overrides[secure_endpoint] = lambda: None
    app.dependency_overrides[get_report_service] = lambda: DummyReportService()

    with TestClient(app) as client:
        response = client.get("/api/v1/reports/abc123?format=json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["report_id"] == "abc123"
    assert payload["data"]["files"]["json"] == "/api/v1/reports/abc123/download?format=json"
    assert payload["data"]["files"]["txt"] == "/api/v1/reports/abc123/download?format=txt"
    assert payload["data"]["files"]["csv"] == "/api/v1/reports/abc123/download?format=csv"
