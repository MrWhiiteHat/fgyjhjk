"""JSON serialization and persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np


def to_jsonable(value: Any) -> Any:
    """Convert numpy/pydantic-like values into JSON-serializable primitives."""
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value.as_posix())
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value


def read_json(path: str | Path, default: Any = None) -> Any:
    """Read JSON file and return default on read/parse failures."""
    target = Path(path)
    if not target.exists() or not target.is_file():
        return default
    try:
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path: str | Path, payload: Dict[str, Any], indent: int = 2) -> Path:
    """Write dictionary payload to JSON file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(payload), handle, indent=indent, ensure_ascii=True)
    return target
