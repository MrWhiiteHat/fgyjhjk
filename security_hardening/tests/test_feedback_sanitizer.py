from __future__ import annotations

from datetime import datetime, timezone

from security_hardening.poisoning.feedback_sanitizer import FeedbackSanitizer


def test_feedback_sanitizer_quarantines_suspicious_records() -> None:
    sanitizer = FeedbackSanitizer()
    now = datetime.now(tz=timezone.utc).isoformat()

    feedback = [
        {
            "feedback_id": "f1",
            "actor_id": "u1",
            "prediction_id": "p1",
            "predicted_label": 1,
            "corrected_label": 0,
            "submitted_at": now,
            "correction_confidence": 0.95,
            "provenance": "api",
        },
        {
            "feedback_id": "f2",
            "actor_id": "u1",
            "prediction_id": "p1",
            "predicted_label": 1,
            "corrected_label": 0,
            "submitted_at": now,
            "correction_confidence": 0.91,
            "provenance": "api",
        },
        {
            "feedback_id": "f3",
            "actor_id": "u3",
            "prediction_id": "p3",
            "predicted_label": 0,
            "corrected_label": 1,
            "submitted_at": now,
            "correction_confidence": 0.20,
            "provenance": "api",
        },
    ]

    result = sanitizer.sanitize(feedback_records=feedback, policy={})

    assert float(result.stats["anomaly_rate"]) > 0.0
    assert len(result.quarantined_records) >= 1
    assert len(result.accepted_records) + len(result.quarantined_records) == len(feedback)


def test_feedback_sanitizer_reasons_exposed() -> None:
    sanitizer = FeedbackSanitizer()
    now = datetime.now(tz=timezone.utc).isoformat()
    feedback = [
        {
            "feedback_id": "x1",
            "actor_id": "ax",
            "prediction_id": "px",
            "predicted_label": 0,
            "corrected_label": 1,
            "submitted_at": now,
            "correction_confidence": 0.99,
            "provenance": "unknown",
        }
    ]

    result = sanitizer.sanitize(feedback_records=feedback, policy={})

    assert len(result.reasons_by_feedback_id) == 1
    reasons = next(iter(result.reasons_by_feedback_id.values()))
    assert "missing_provenance" in reasons
