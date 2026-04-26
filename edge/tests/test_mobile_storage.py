from __future__ import annotations

from pathlib import Path


EDGE_DIR = Path(__file__).resolve().parents[1]
STORAGE_SERVICE_PATH = EDGE_DIR / "mobile" / "app" / "src" / "services" / "storageService.ts"


def test_storage_service_exposes_required_api_methods() -> None:
    text = STORAGE_SERVICE_PATH.read_text(encoding="utf-8")

    required_methods = [
        "getSettings",
        "setSettings",
        "getHistory",
        "setHistory",
        "getQueue",
        "setQueue",
        "clearHistory",
        "clearQueue",
        "estimateStorageUsageBytes",
    ]

    for method_name in required_methods:
        assert f"async {method_name}" in text


def test_storage_service_uses_expected_keys() -> None:
    text = STORAGE_SERVICE_PATH.read_text(encoding="utf-8")

    assert "STORAGE_KEYS.SETTINGS" in text
    assert "STORAGE_KEYS.HISTORY" in text
    assert "STORAGE_KEYS.OFFLINE_QUEUE" in text
    assert "JSON.parse" in text
    assert "JSON.stringify" in text
