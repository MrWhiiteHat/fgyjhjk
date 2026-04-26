"""Table export helpers for reports and machine-readable artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from evaluation.utils.io import save_dataframe_csv, save_dict_json


def export_dataframe(
    table: pd.DataFrame,
    csv_path: str | Path,
    json_path: str | Path | None = None,
) -> Dict[str, str]:
    """Export dataframe to CSV and optional JSON record list."""
    csv_file = save_dataframe_csv(table, csv_path)
    outputs = {"csv": str(csv_file.as_posix())}

    if json_path is not None:
        save_dict_json({"records": table.to_dict(orient="records")}, json_path)
        outputs["json"] = str(Path(json_path).as_posix())

    return outputs


def export_metrics_table(metrics: Dict[str, Any], output_csv_path: str | Path) -> Path:
    """Flatten metrics dictionary to a metric-value CSV table."""
    rows = []
    for key, value in metrics.items():
        if key == "confusion_matrix":
            continue
        rows.append({"metric": key, "value": value})

    table = pd.DataFrame(rows)
    return save_dataframe_csv(table, output_csv_path)


def dataframe_to_text_table(table: pd.DataFrame, max_rows: int = 20) -> str:
    """Render dataframe as plain text table for human-readable reports."""
    if table.empty:
        return "(empty)"

    clipped = table.head(max_rows)
    return clipped.to_string(index=False)
