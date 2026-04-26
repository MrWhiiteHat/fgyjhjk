from __future__ import annotations

from datetime import datetime, timedelta, timezone

from security_hardening.extraction.query_pattern_detector import QueryPatternDetector, QueryRecord


def test_query_pattern_detector_detects_bulk_enumeration() -> None:
    detector = QueryPatternDetector()
    now = datetime.now(tz=timezone.utc)

    history = []
    for idx in range(65):
        history.append(
            QueryRecord(
                timestamp=(now - timedelta(seconds=idx)).isoformat(),
                input_digest=f"{idx:032x}",
                confidence=0.51,
                threshold=0.5,
            )
        )

    result = detector.analyze(history=history, bulk_unique_inputs_threshold=50)

    assert result.risk_score >= 0.15
    assert "bulk_enumeration_behavior" in result.reason_codes


def test_query_pattern_detector_detects_near_duplicate_probing() -> None:
    detector = QueryPatternDetector()
    now = datetime.now(tz=timezone.utc)

    history = [
        QueryRecord(timestamp=now.isoformat(), input_digest="aaaaaaaaaaaaaaaa", confidence=0.90, threshold=0.4),
        QueryRecord(
            timestamp=(now - timedelta(seconds=1)).isoformat(),
            input_digest="aaaaaaaaaaaaaaab",
            confidence=0.89,
            threshold=0.41,
        ),
        QueryRecord(
            timestamp=(now - timedelta(seconds=2)).isoformat(),
            input_digest="aaaaaaaaaaaaaaac",
            confidence=0.88,
            threshold=0.42,
        ),
        QueryRecord(
            timestamp=(now - timedelta(seconds=3)).isoformat(),
            input_digest="aaaaaaaaaaaaaaad",
            confidence=0.87,
            threshold=0.43,
        ),
    ]

    result = detector.analyze(history=history, duplicate_hamming_threshold=1, threshold_sweep_unique_count=4)

    assert result.risk_score > 0.0
    assert "repeated_tiny_modifications" in result.reason_codes
