from __future__ import annotations

import io

from PIL import Image

from security_hardening.defenses.input_guard import InputGuard, InputGuardConfig


def _jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    image = Image.new("RGB", (width, height), color=(120, 80, 30))
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


def test_input_guard_allows_valid_image() -> None:
    guard = InputGuard()

    decision = guard.evaluate(
        filename="sample.jpg",
        payload=_jpeg_bytes(),
        claimed_mime="image/jpeg",
        source_key="tenant_a",
    )

    assert decision.action in {"allow", "allow_with_warning"}
    assert decision.reason_codes in [["ok"], ["warning_only"]]


def test_input_guard_blocks_corrupted_payload() -> None:
    guard = InputGuard()

    decision = guard.evaluate(
        filename="bad.jpg",
        payload=b"not_a_jpeg_payload",
        claimed_mime="image/jpeg",
        source_key="tenant_b",
    )

    assert decision.action == "block"
    assert "malformed_content" in decision.reason_codes


def test_input_guard_repeated_corrupted_header_escalates() -> None:
    guard = InputGuard(config=InputGuardConfig(repeated_corrupted_header_threshold=2))
    malformed = b"same_corrupt_header"

    first = guard.evaluate(
        filename="bad1.jpg",
        payload=malformed,
        claimed_mime="image/jpeg",
        source_key="repeat_source",
    )
    second = guard.evaluate(
        filename="bad2.jpg",
        payload=malformed,
        claimed_mime="image/jpeg",
        source_key="repeat_source",
    )

    assert first.action == "block"
    assert second.action == "block"
    assert "repeated_corrupted_header" in second.reason_codes
