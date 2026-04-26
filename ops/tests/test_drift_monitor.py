from pathlib import Path

import yaml

from ops.monitoring.drift_monitor import DriftMonitor


def _records(n: int, label: str) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "brightness_score": 0.4 + (i * 0.001),
                "blur_score": 0.2 + (i * 0.001),
                "width": 224,
                "height": 224,
                "face_confidence": 0.9,
                "probability": 0.8,
                "predicted_label": label,
                "predicted_probability": 0.8,
                "prediction_success": True,
                "upload_size_bytes": 10000,
                "malformed": False,
                "corrupt": False,
                "unreadable": False,
                "rejected": False,
            }
        )
    return rows


def test_drift_monitor_runs_and_writes_reports(tmp_path):
    reference_dir = tmp_path / "references"
    report_dir = tmp_path / "reports"
    history_path = tmp_path / "drift_history.jsonl"

    config = {
        "feature_drift_threshold": 0.05,
        "prediction_drift_threshold": 0.05,
        "max_histogram_bins": 10,
        "reference_store_path": str(reference_dir.as_posix()),
        "report_output_dir": str(report_dir.as_posix()),
        "drift_history_path": str(history_path.as_posix()),
        "feature_list": [
            "brightness_score",
            "blur_score",
            "width",
            "height",
            "face_confidence",
            "probability",
        ],
    }
    config_path = tmp_path / "drift_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    monitor = DriftMonitor(drift_config_path=str(config_path))

    reference_payload = monitor.reference_builder.build_from_records(
        records=_records(40, "REAL"),
        model_version="v1",
        source="unit-test",
    )

    result = monitor.run_drift_check(
        current_records=_records(40, "FAKE"),
        model_version="v1",
        reference_payload=reference_payload,
    )

    assert result["model_version"] == "v1"
    assert Path(result["report_paths"]["json"]).exists()
    assert Path(result["report_paths"]["txt"]).exists()
    assert Path(result["report_paths"]["csv"]).exists()
    assert history_path.exists()
