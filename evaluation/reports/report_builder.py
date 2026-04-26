"""Experiment report builder for machine-readable and human-readable outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from evaluation.reports.export_tables import export_metrics_table
from evaluation.utils.helpers import now_timestamp
from evaluation.utils.io import save_dict_json, write_text


def build_summary_payload(
    experiment_name: str,
    model_artifact_used: str,
    split_evaluated: str,
    dataset_size: int,
    threshold_used: float,
    calibration_enabled: bool,
    metrics: Dict[str, Any],
    confusion_summary: Dict[str, Any],
    failure_summary: Dict[str, Any],
    runtime_statistics: Dict[str, Any],
    additional_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build consolidated summary payload for JSON and text reporting."""
    payload: Dict[str, Any] = {
        "generated_at": now_timestamp(),
        "experiment_name": str(experiment_name),
        "model_artifact_used": str(model_artifact_used),
        "split_evaluated": str(split_evaluated),
        "dataset_size": int(dataset_size),
        "threshold_used": float(threshold_used),
        "calibration_enabled": bool(calibration_enabled),
        "metrics": metrics,
        "confusion_summary": confusion_summary,
        "top_failure_cases": failure_summary,
        "runtime_statistics": runtime_statistics,
    }

    if additional_context:
        payload["additional_context"] = additional_context

    return payload


def build_human_readable_report_text(summary_payload: Dict[str, Any]) -> str:
    """Render summary payload into readable multiline report text."""
    metrics = summary_payload.get("metrics", {})
    confusion = summary_payload.get("confusion_summary", {})
    failure = summary_payload.get("top_failure_cases", {})
    runtime = summary_payload.get("runtime_statistics", {})

    lines = [
        "Evaluation Summary Report",
        "========================",
        f"Generated At: {summary_payload.get('generated_at', '')}",
        f"Experiment Name: {summary_payload.get('experiment_name', '')}",
        f"Model Artifact Used: {summary_payload.get('model_artifact_used', '')}",
        f"Split Evaluated: {summary_payload.get('split_evaluated', '')}",
        f"Dataset Size: {summary_payload.get('dataset_size', 0)}",
        f"Threshold Used: {summary_payload.get('threshold_used', 0.5):.6f}",
        f"Calibration Enabled: {summary_payload.get('calibration_enabled', False)}",
        "",
        "Metrics",
        "-------",
    ]

    for key, value in metrics.items():
        if key == "confusion_matrix":
            continue
        lines.append(f"{key}: {value}")

    lines.extend(
        [
            "",
            "Confusion Summary",
            "-----------------",
            f"TP: {confusion.get('tp', 0)}",
            f"TN: {confusion.get('tn', 0)}",
            f"FP: {confusion.get('fp', 0)}",
            f"FN: {confusion.get('fn', 0)}",
            "",
            "Failure Analysis",
            "----------------",
            f"False Positives: {failure.get('num_false_positives', 0)}",
            f"False Negatives: {failure.get('num_false_negatives', 0)}",
            f"Wrong Predictions: {failure.get('num_wrong_predictions', 0)}",
            "",
            "Runtime Statistics",
            "------------------",
        ]
    )

    for key, value in runtime.items():
        lines.append(f"{key}: {value}")

    lines.append("")
    return "\n".join(lines)


def save_reports(
    output_reports_dir: str | Path,
    summary_payload: Dict[str, Any],
) -> Dict[str, str]:
    """Persist summary report files (TXT/JSON) and metrics table CSV."""
    report_dir = Path(output_reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_json = report_dir / "summary_report.json"
    summary_txt = report_dir / "summary_report.txt"
    metrics_csv = report_dir / "metrics_table.csv"

    save_dict_json(summary_payload, summary_json)
    write_text(summary_txt, build_human_readable_report_text(summary_payload))
    export_metrics_table(summary_payload.get("metrics", {}), metrics_csv)

    return {
        "summary_report_json": str(summary_json.as_posix()),
        "summary_report_txt": str(summary_txt.as_posix()),
        "metrics_table_csv": str(metrics_csv.as_posix()),
    }
