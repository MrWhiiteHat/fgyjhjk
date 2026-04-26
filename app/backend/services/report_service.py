"""Report persistence service with indexing and lookup support."""

from __future__ import annotations

import csv
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.backend.config import get_settings
from app.backend.core.exceptions import ReportNotFoundError
from app.backend.utils.helpers import ensure_dir
from app.backend.utils.json_utils import read_json, write_json
from app.backend.utils.logger import configure_logger


class ReportService:
    """Persist and retrieve structured prediction reports."""

    _instance: "ReportService | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = configure_logger("backend.report_service", self.settings.LOG_LEVEL, f"{self.settings.OUTPUT_DIR}/logs")
        self.base_dir = ensure_dir(Path(self.settings.OUTPUT_DIR) / "reports")
        self.index_path = self.base_dir / "report_index.json"
        self._lock = threading.RLock()

        if not self.index_path.exists():
            write_json(self.index_path, {"reports": {}})

    @classmethod
    def get_instance(cls) -> "ReportService":
        """Get singleton report service instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = ReportService()
        return cls._instance

    def _read_index(self) -> Dict[str, Any]:
        payload = read_json(self.index_path, default={"reports": {}})
        if not isinstance(payload, dict) or "reports" not in payload:
            payload = {"reports": {}}
        return payload

    def _write_index(self, payload: Dict[str, Any]) -> None:
        write_json(self.index_path, payload)

    def create_report(
        self,
        request_metadata: Dict[str, Any],
        file_metadata: Dict[str, Any],
        prediction_results: Dict[str, Any],
        explanation_outputs: Dict[str, Any] | None,
        model_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create report artifacts (JSON, TXT, CSV) and register index metadata."""
        request_id = str(request_metadata.get("request_id", "unknown-request"))
        started = time.perf_counter()
        self.logger.info("request_id=%s stage=report_generation_started", request_id)

        report_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        report_dir = ensure_dir(self.base_dir / report_id)
        report_json = report_dir / "report.json"
        report_txt = report_dir / "report.txt"
        report_csv = report_dir / "prediction_rows.csv"

        payload = {
            "report_id": report_id,
            "created_at": created_at,
            "request_metadata": request_metadata,
            "file_metadata": file_metadata,
            "prediction_results": prediction_results,
            "explanation_outputs": explanation_outputs or {},
            "model_metadata": model_metadata,
        }

        write_json(report_json, payload)

        txt_lines = [
            "Prediction Report",
            "=================",
            f"report_id: {report_id}",
            f"created_at: {created_at}",
            f"request_id: {request_metadata.get('request_id', '')}",
            f"input_file: {file_metadata.get('original_filename', '')}",
            f"predicted_label: {prediction_results.get('predicted_label', '')}",
            f"predicted_probability: {prediction_results.get('predicted_probability', '')}",
            f"threshold_used: {prediction_results.get('threshold_used', '')}",
            f"model_name: {model_metadata.get('model_name', '')}",
            f"artifact_path: {model_metadata.get('artifact_path', '')}",
        ]
        report_txt.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

        rows = prediction_results.get("rows", [])
        if isinstance(rows, list) and rows:
            keys = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
            with report_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        else:
            with report_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["field", "value"])
                writer.writeheader()
                for key, value in prediction_results.items():
                    if key == "rows":
                        continue
                    writer.writerow({"field": key, "value": value})

        entry = {
            "report_id": report_id,
            "created_at": created_at,
            "request_id": request_metadata.get("request_id", ""),
            "json_path": str(report_json.as_posix()),
            "txt_path": str(report_txt.as_posix()),
            "csv_path": str(report_csv.as_posix()),
            "expires_at": None,
        }

        with self._lock:
            index = self._read_index()
            index["reports"][report_id] = entry
            self._write_index(index)

        self.logger.info(
            "request_id=%s stage=report_generation_finished report_id=%s duration_ms=%.2f",
            request_id,
            report_id,
            (time.perf_counter() - started) * 1000.0,
        )

        return {
            "report_id": report_id,
            "metadata": entry,
            "files": {
                "json": str(report_json.as_posix()),
                "txt": str(report_txt.as_posix()),
                "csv": str(report_csv.as_posix()),
            },
        }

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """Lookup report metadata and resolved artifact paths by report_id."""
        with self._lock:
            index = self._read_index()
            entry = index.get("reports", {}).get(report_id)

        if not entry:
            raise ReportNotFoundError(f"Report not found: {report_id}")

        json_path = Path(entry["json_path"])
        txt_path = Path(entry["txt_path"])
        csv_path = Path(entry["csv_path"])

        if not json_path.exists():
            raise ReportNotFoundError(f"Report JSON file missing for report_id={report_id}")

        return {
            "report_id": report_id,
            "metadata": entry,
            "files": {
                "json": str(json_path.as_posix()),
                "txt": str(txt_path.as_posix()) if txt_path.exists() else "",
                "csv": str(csv_path.as_posix()) if csv_path.exists() else "",
            },
        }

    def cleanup_expired(self) -> int:
        """Placeholder cleanup policy; returns removed report count."""
        # Expiration policy is intentionally explicit and conservative; disabled by default.
        return 0
