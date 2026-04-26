"""Drift report generation in JSON, TXT, and CSV formats."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Dict, List


class DriftReportWriter:
    """Writes drift analysis output into versioned report artifacts."""

    def __init__(self, output_dir: str = "app/backend/outputs/ops/drift/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _stamp() -> str:
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    def write_report(
        self,
        model_version: str,
        window_start: str,
        window_end: str,
        feature_summary: Dict[str, object],
        prediction_summary: Dict[str, object],
        data_quality_summary: Dict[str, object],
        triggered_alerts: List[Dict[str, object]],
        recommended_action: str,
    ) -> Dict[str, str]:
        stamp = self._stamp()
        report_id = f"drift_{model_version}_{stamp}"
        report_dir = self.output_dir / str(model_version)
        report_dir.mkdir(parents=True, exist_ok=True)

        json_path = report_dir / f"{report_id}.json"
        txt_path = report_dir / f"{report_id}.txt"
        csv_path = report_dir / f"{report_id}.csv"

        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model_version": str(model_version),
            "window": {"start": window_start, "end": window_end},
            "feature_drift_summary": feature_summary,
            "prediction_drift_summary": prediction_summary,
            "data_quality_summary": data_quality_summary,
            "triggered_alerts": triggered_alerts,
            "recommended_action": recommended_action,
        }

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

        text_lines = [
            "Drift Monitoring Report",
            "=======================",
            f"timestamp: {payload['timestamp']}",
            f"model_version: {model_version}",
            f"window_start: {window_start}",
            f"window_end: {window_end}",
            "",
            f"feature_drift_score: {feature_summary.get('overall_drift_score', 0.0)}",
            f"prediction_drift_score: {prediction_summary.get('drift_score', 0.0)}",
            f"data_quality_alert: {data_quality_summary.get('alert', False)}",
            f"triggered_alerts: {len(triggered_alerts)}",
            f"recommended_action: {recommended_action}",
        ]
        txt_path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["section", "key", "value"],
            )
            writer.writeheader()
            for key, value in feature_summary.items():
                if key == "per_feature":
                    continue
                writer.writerow({"section": "feature", "key": key, "value": value})
            for key, value in prediction_summary.items():
                writer.writerow({"section": "prediction", "key": key, "value": value})
            for key, value in data_quality_summary.items():
                if key == "anomalies":
                    continue
                writer.writerow({"section": "quality", "key": key, "value": value})
            for index, alert in enumerate(triggered_alerts, start=1):
                writer.writerow({"section": "alert", "key": f"alert_{index}", "value": json.dumps(alert, sort_keys=True)})

        return {
            "json": str(json_path.as_posix()),
            "txt": str(txt_path.as_posix()),
            "csv": str(csv_path.as_posix()),
        }
