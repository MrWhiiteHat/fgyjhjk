"""Data quality monitoring for upload and inference pipeline health."""

from __future__ import annotations

from typing import Dict, List


class DataQualityMonitor:
    """Computes quality ratios and anomaly flags from request metadata."""

    def __init__(
        self,
        malformed_rate_threshold: float = 0.1,
        corrupt_rate_threshold: float = 0.05,
        failure_rate_threshold: float = 0.05,
    ) -> None:
        self.malformed_rate_threshold = float(malformed_rate_threshold)
        self.corrupt_rate_threshold = float(corrupt_rate_threshold)
        self.failure_rate_threshold = float(failure_rate_threshold)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    def evaluate(self, records: List[Dict[str, object]]) -> Dict[str, object]:
        total = len(records)

        malformed = sum(1 for record in records if bool(record.get("malformed", False)))
        rejected = sum(1 for record in records if bool(record.get("rejected", False)))
        corrupt = sum(1 for record in records if bool(record.get("corrupt", False)))
        unreadable = sum(1 for record in records if bool(record.get("unreadable", False)))
        prediction_failed = sum(1 for record in records if not bool(record.get("prediction_success", True)))
        oversized = sum(1 for record in records if bool(record.get("oversized", False)))

        upload_sizes = [int(record.get("upload_size_bytes", 0)) for record in records if int(record.get("upload_size_bytes", 0)) > 0]
        widths = [int(record.get("width", 0)) for record in records if int(record.get("width", 0)) > 0]
        heights = [int(record.get("height", 0)) for record in records if int(record.get("height", 0)) > 0]

        avg_upload_size = sum(upload_sizes) / len(upload_sizes) if upload_sizes else 0.0
        avg_width = sum(widths) / len(widths) if widths else 0.0
        avg_height = sum(heights) / len(heights) if heights else 0.0

        malformed_rate = self._ratio(malformed, total)
        corrupt_rate = self._ratio(corrupt + unreadable, total)
        failure_rate = self._ratio(prediction_failed, total)

        anomalies: List[Dict[str, object]] = []
        if malformed_rate >= self.malformed_rate_threshold:
            anomalies.append({"type": "malformed_surge", "rate": round(malformed_rate, 6)})
        if corrupt_rate >= self.corrupt_rate_threshold:
            anomalies.append({"type": "corrupt_surge", "rate": round(corrupt_rate, 6)})
        if failure_rate >= self.failure_rate_threshold:
            anomalies.append({"type": "prediction_failure_surge", "rate": round(failure_rate, 6)})
        if oversized >= 5:
            anomalies.append({"type": "oversized_attempt_surge", "count": oversized})

        return {
            "method": "data_quality_monitor",
            "total_records": total,
            "malformed_count": malformed,
            "rejected_count": rejected,
            "corrupt_count": corrupt,
            "unreadable_count": unreadable,
            "prediction_failed_count": prediction_failed,
            "oversized_count": oversized,
            "malformed_rate": round(malformed_rate, 6),
            "corrupt_rate": round(corrupt_rate, 6),
            "prediction_failure_rate": round(failure_rate, 6),
            "average_upload_size_bytes": round(avg_upload_size, 2),
            "average_width": round(avg_width, 2),
            "average_height": round(avg_height, 2),
            "anomalies": anomalies,
            "alert": bool(anomalies),
        }
