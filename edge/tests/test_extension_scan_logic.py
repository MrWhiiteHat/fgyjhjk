from __future__ import annotations

from pathlib import Path


EDGE_DIR = Path(__file__).resolve().parents[1]
DOM_SCANNER_PATH = EDGE_DIR / "browser_extension" / "src" / "content" / "domScanner.ts"
CONTENT_PATH = EDGE_DIR / "browser_extension" / "src" / "content" / "content.ts"
VALIDATORS_PATH = EDGE_DIR / "browser_extension" / "src" / "lib" / "validators.ts"


def test_dom_scanner_has_scan_limit_and_dedupe_logic() -> None:
    text = DOM_SCANNER_PATH.read_text(encoding="utf-8")

    assert "collectImageCandidates" in text
    assert "candidates.length >= scanLimit" in text
    assert "scannedCache" in text
    assert "shouldScanCandidate" in text
    assert "resetScanCache" in text


def test_content_script_has_overlay_and_scan_action_handling() -> None:
    text = CONTENT_PATH.read_text(encoding="utf-8")

    assert "data-edge-overlay" in text
    assert "SCAN_PAGE" in text
    assert "overlayEnabled" in text
    assert "saveLastResults" in text


def test_validators_define_scan_limit_boundaries() -> None:
    text = VALIDATORS_PATH.read_text(encoding="utf-8")

    assert "MAX_SCAN_LIMIT" in text
    assert "scanLimit must be between 1 and" in text
