"""Reference baseline creation and versioned persistence for drift checks."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


class ReferenceBuilder:
    """Builds immutable versioned reference windows for drift monitoring."""

    def __init__(self, base_path: str = "ops/drift/state/references") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_stamp() -> str:
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    @staticmethod
    def _extract_reference_records(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
        allowed = {
            "brightness_score",
            "blur_score",
            "width",
            "height",
            "face_confidence",
            "probability",
            "predicted_label",
            "predicted_probability",
            "prediction_success",
            "upload_size_bytes",
            "malformed",
            "corrupt",
            "unreadable",
            "rejected",
        }
        records = []
        for row in rows:
            records.append({key: row.get(key) for key in allowed if key in row})
        return records

    def build_from_records(
        self,
        records: List[Dict[str, object]],
        model_version: str,
        source: str,
        notes: str = "",
    ) -> Dict[str, object]:
        """Build reference payload from provided records and persist versioned artifact."""
        stamp = self._now_stamp()
        payload = {
            "reference_id": f"{model_version}_{stamp}",
            "model_version": str(model_version),
            "source": str(source),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "window": {
                "start": None,
                "end": None,
                "days": None,
            },
            "notes": str(notes),
            "records": self._extract_reference_records(records),
        }
        self._persist(payload)
        return payload

    def build_from_validation_outputs(
        self,
        validation_outputs_dir: str,
        model_version: str,
        notes: str = "built from validation outputs",
    ) -> Dict[str, object]:
        """Build reference from existing validation/test prediction CSV files."""
        root = Path(validation_outputs_dir)
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Validation output path does not exist: {root}")

        rows: List[Dict[str, object]] = []
        for csv_path in sorted(root.rglob("*.csv")):
            try:
                with csv_path.open("r", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        rows.append(dict(row))
            except OSError:
                continue

        if not rows:
            raise ValueError(f"No prediction CSV rows found under {root}")

        payload = self.build_from_records(
            records=rows,
            model_version=model_version,
            source=str(root.as_posix()),
            notes=notes,
        )
        payload["window"] = {
            "start": None,
            "end": None,
            "days": None,
        }
        self._persist(payload)
        return payload

    def _persist(self, payload: Dict[str, object]) -> Path:
        model_version = str(payload["model_version"])
        reference_id = str(payload["reference_id"])
        model_dir = self.base_path / model_version
        model_dir.mkdir(parents=True, exist_ok=True)

        target = model_dir / f"{reference_id}.json"
        if target.exists():
            raise FileExistsError(f"Reference already exists and cannot be overwritten: {target}")

        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return target

    def load_reference(self, reference_path: str) -> Dict[str, object]:
        path = Path(reference_path)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload

    def get_latest_reference(self, model_version: str) -> Optional[Dict[str, object]]:
        model_dir = self.base_path / str(model_version)
        if not model_dir.exists() or not model_dir.is_dir():
            return None
        candidates = sorted(model_dir.glob("*.json"))
        if not candidates:
            return None
        latest_path = candidates[-1]
        return self.load_reference(str(latest_path))

    def validate_reference(self, payload: Dict[str, object]) -> Dict[str, object]:
        records = payload.get("records", [])
        checks = {
            "has_reference_id": bool(payload.get("reference_id")),
            "has_model_version": bool(payload.get("model_version")),
            "has_records": isinstance(records, list) and len(records) > 0,
            "records_are_dicts": isinstance(records, list) and all(isinstance(row, dict) for row in records),
        }
        checks["valid"] = all(checks.values())
        return checks
