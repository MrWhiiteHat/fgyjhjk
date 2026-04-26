"""Scheduled drift monitoring orchestration across feature/prediction/quality checks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event
from typing import Callable, Dict, List, Optional

import yaml

from ops.drift.data_quality_monitor import DataQualityMonitor
from ops.drift.drift_report import DriftReportWriter
from ops.drift.feature_drift import FeatureDriftDetector
from ops.drift.prediction_drift import PredictionDriftDetector
from ops.drift.reference_builder import ReferenceBuilder


class DriftMonitor:
    """Runs drift checks against immutable references and records history."""

    def __init__(self, drift_config_path: str = "ops/configs/drift_config.yaml") -> None:
        self.drift_config_path = Path(drift_config_path)
        self.config = self._load_config(self.drift_config_path)

        self.feature_threshold = float(self.config.get("feature_drift_threshold", 0.2))
        self.prediction_threshold = float(self.config.get("prediction_drift_threshold", 0.15))

        self.feature_detector = FeatureDriftDetector(
            psi_threshold=self.feature_threshold,
            ks_threshold=self.feature_threshold,
            bins=int(self.config.get("max_histogram_bins", 10)),
        )
        self.prediction_detector = PredictionDriftDetector()
        self.quality_monitor = DataQualityMonitor()
        self.reference_builder = ReferenceBuilder(base_path=str(self.config.get("reference_store_path", "ops/drift/state/references")))
        self.report_writer = DriftReportWriter(output_dir=str(self.config.get("report_output_dir", "app/backend/outputs/ops/drift/reports")))

        self.history_path = Path(str(self.config.get("drift_history_path", "app/backend/outputs/ops/drift/drift_history.jsonl")))
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        self.features = list(self.config.get("feature_list", []))
        if not self.features:
            self.features = [
                "brightness_score",
                "blur_score",
                "width",
                "height",
                "face_confidence",
                "probability",
            ]

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _save_history(self, payload: Dict[str, object]) -> None:
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    @staticmethod
    def _copy_reference(reference_payload: Dict[str, object]) -> Dict[str, object]:
        return json.loads(json.dumps(reference_payload))

    def run_drift_check(
        self,
        current_records: List[Dict[str, object]],
        model_version: str,
        reference_payload: Optional[Dict[str, object]] = None,
        reference_path: Optional[str] = None,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> Dict[str, object]:
        """Execute one drift check cycle and write reports/history artifacts."""
        if reference_payload is None:
            if reference_path:
                reference_payload = self.reference_builder.load_reference(reference_path)
            else:
                reference_payload = self.reference_builder.get_latest_reference(model_version)

        if reference_payload is None:
            raise ValueError(
                f"No reference available for model version '{model_version}'. Build a reference before drift checks."
            )

        reference_snapshot = self._copy_reference(reference_payload)
        reference_records = list(reference_snapshot.get("records", []))

        feature_summary = self.feature_detector.compare(
            reference_records=reference_records,
            current_records=current_records,
            features=self.features,
        )
        prediction_summary = self.prediction_detector.compare(
            reference_records=reference_records,
            current_records=current_records,
        )
        quality_summary = self.quality_monitor.evaluate(current_records)

        triggered_alerts: List[Dict[str, object]] = []
        if float(feature_summary.get("overall_drift_score", 0.0)) >= self.feature_threshold:
            triggered_alerts.append(
                {
                    "type": "feature_drift",
                    "severity": "warning",
                    "score": feature_summary.get("overall_drift_score", 0.0),
                    "threshold": self.feature_threshold,
                }
            )

        if float(prediction_summary.get("drift_score", 0.0)) >= self.prediction_threshold:
            triggered_alerts.append(
                {
                    "type": "prediction_drift",
                    "severity": "critical" if prediction_summary.get("collapse_detected", False) else "warning",
                    "score": prediction_summary.get("drift_score", 0.0),
                    "threshold": self.prediction_threshold,
                }
            )

        if bool(quality_summary.get("alert", False)):
            triggered_alerts.append(
                {
                    "type": "data_quality",
                    "severity": "warning",
                    "anomalies": quality_summary.get("anomalies", []),
                }
            )

        recommendation = "continue_monitoring"
        if any(alert.get("severity") == "critical" for alert in triggered_alerts):
            recommendation = "investigate_and_consider_rollback"
        elif triggered_alerts:
            recommendation = "investigate_and_tighten_validation"

        report_paths = self.report_writer.write_report(
            model_version=model_version,
            window_start=window_start or self._now_iso(),
            window_end=window_end or self._now_iso(),
            feature_summary=feature_summary,
            prediction_summary=prediction_summary,
            data_quality_summary=quality_summary,
            triggered_alerts=triggered_alerts,
            recommended_action=recommendation,
        )

        result = {
            "timestamp": self._now_iso(),
            "model_version": model_version,
            "window_start": window_start,
            "window_end": window_end,
            "feature_summary": feature_summary,
            "prediction_summary": prediction_summary,
            "data_quality_summary": quality_summary,
            "triggered_alerts": triggered_alerts,
            "recommended_action": recommendation,
            "report_paths": report_paths,
        }

        self._save_history(result)
        return result

    def run_scheduled(
        self,
        stop_event: Event,
        current_data_provider: Callable[[], List[Dict[str, object]]],
        model_version_provider: Callable[[], str],
        max_iterations: int | None = None,
    ) -> List[Dict[str, object]]:
        """Run drift checks on configured interval until stop event is set."""
        interval_seconds = max(1, int(float(self.config.get("drift_check_interval_hours", 6)) * 3600))
        min_samples = int(self.config.get("min_samples_for_check", 100))

        results: List[Dict[str, object]] = []
        iterations = 0
        while not stop_event.is_set():
            current_records = current_data_provider()
            if len(current_records) >= min_samples:
                model_version = str(model_version_provider())
                result = self.run_drift_check(current_records=current_records, model_version=model_version)
                results.append(result)

            iterations += 1
            if max_iterations is not None and iterations >= int(max_iterations):
                break

            stop_event.wait(interval_seconds)

        return results
