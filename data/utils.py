"""Shared utilities for the deepfake data pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import yaml

REAL_LABEL = 0
FAKE_LABEL = 1


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load YAML configuration from disk."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ValueError("config.yaml must contain a top-level dictionary")
    return config


def ensure_required_structure(config: Dict) -> None:
    """Create the exact required dataset directory structure."""
    required_dirs = [
        "dataset/raw/faceforensics",
        "dataset/raw/celebdf",
        "dataset/raw/dfdc",
        "dataset/raw/custom",
        "dataset/processed/real",
        "dataset/processed/fake",
        "dataset/frames/real",
        "dataset/frames/fake",
        "dataset/metadata",
        "dataset/logs",
    ]

    for directory in required_dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)

    # Ensure required metadata files exist with headers when needed.
    labels_path = Path(config["paths"]["metadata"]["labels"])
    if not labels_path.exists():
        write_csv_rows(labels_path, ["filepath", "label", "dataset"], [])


def setup_logger(log_file: Path) -> logging.Logger:
    """Create a consistent logger for all modules."""
    logger = logging.getLogger("data_pipeline")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def sanitize_name(name: str) -> str:
    """Normalize a file stem to safe ASCII-friendly characters."""
    safe = []
    for char in name:
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "item"


def discover_files_by_extensions(root: Path, extensions: Sequence[str]) -> List[Path]:
    """Recursively discover files that match allowed extensions."""
    if not root.exists():
        return []

    extension_set = {ext.lower() for ext in extensions}
    matches: List[Path] = []
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extension_set:
            matches.append(file_path)
    return sorted(matches)


def compute_md5(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute MD5 hash for deduplication and integrity checks."""
    digest = hashlib.md5()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def unique_destination_path(destination_dir: Path, filename: str) -> Path:
    """Create a unique path by appending a numeric suffix on collisions."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    candidate = destination_dir / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        retry_path = destination_dir / f"{stem}_{counter}{suffix}"
        if not retry_path.exists():
            return retry_path
        counter += 1


def copy_with_integrity(source: Path, destination: Path, overwrite: bool = False) -> Path:
    """Copy a file while preserving metadata and avoiding unnecessary duplication."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not overwrite:
        same_size = source.stat().st_size == destination.stat().st_size
        if same_size and compute_md5(source) == compute_md5(destination):
            return destination

    shutil.copy2(source, destination)
    return destination


def build_auth_headers(auth_cfg: Optional[Dict]) -> Dict[str, str]:
    """Build HTTP authentication headers from config."""
    if not auth_cfg:
        return {}

    headers: Dict[str, str] = {}
    auth_type = str(auth_cfg.get("type", "none")).lower().strip()

    if auth_type == "bearer" and auth_cfg.get("token"):
        headers["Authorization"] = f"Bearer {auth_cfg['token']}"
    elif auth_type == "basic" and auth_cfg.get("username") and auth_cfg.get("password"):
        token = f"{auth_cfg['username']}:{auth_cfg['password']}".encode("utf-8")
        import base64

        headers["Authorization"] = f"Basic {base64.b64encode(token).decode('ascii')}"
    elif auth_type == "header":
        key = auth_cfg.get("key")
        value = auth_cfg.get("value")
        if key and value:
            headers[str(key)] = str(value)

    return headers


def download_file_with_resume(
    url: str,
    destination: Path,
    headers: Optional[Dict[str, str]] = None,
    chunk_size: int = 8 * 1024 * 1024,
    timeout: int = 60,
    retries: int = 3,
) -> Path:
    """Download a file with HTTP range resume support."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, retries + 1):
        request_headers: Dict[str, str] = dict(headers or {})
        existing_size = temp_path.stat().st_size if temp_path.exists() else 0
        if existing_size > 0:
            request_headers["Range"] = f"bytes={existing_size}-"

        try:
            with requests.get(url, headers=request_headers, stream=True, timeout=timeout) as response:
                if response.status_code == 416 and temp_path.exists():
                    shutil.move(str(temp_path), str(destination))
                    return destination

                response.raise_for_status()

                # If server ignores range and returns full content, restart from scratch.
                if existing_size > 0 and response.status_code == 200 and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                    existing_size = 0

                mode = "ab" if existing_size > 0 and response.status_code == 206 else "wb"
                with temp_path.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            handle.write(chunk)

            shutil.move(str(temp_path), str(destination))
            return destination
        except Exception:
            if attempt == retries:
                raise

    return destination


def extract_archive_if_needed(archive_path: Path, target_dir: Path) -> bool:
    """Extract archive files and return True when extraction happened."""
    suffixes = "".join(archive_path.suffixes).lower()
    extractable = (
        suffixes.endswith(".zip")
        or suffixes.endswith(".tar")
        or suffixes.endswith(".tar.gz")
        or suffixes.endswith(".tgz")
        or suffixes.endswith(".tar.xz")
    )
    if not extractable:
        return False

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(archive_path), str(target_dir))
    return True


def extract_archives_in_directory(root_dir: Path, logger: logging.Logger) -> None:
    """Extract all supported archives discovered under a directory."""
    for file_path in root_dir.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            if extract_archive_if_needed(file_path, file_path.parent):
                logger.info("Extracted archive: %s", file_path)
        except Exception as exc:
            logger.error("Failed to extract archive %s: %s", file_path, exc)


def run_command(command: List[str], logger: logging.Logger, cwd: Optional[Path] = None) -> int:
    """Run a subprocess command and write output to logs."""
    logger.info("Running command: %s", " ".join(command))
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        logger.error("Command not found: %s", command[0])
        return 127
    except Exception as exc:
        logger.error("Command failed to start (%s): %s", " ".join(command), exc)
        return 1

    if result.stdout:
        logger.info(result.stdout.strip())
    if result.stderr:
        logger.warning(result.stderr.strip())

    return result.returncode


def read_json_file(file_path: Path) -> Dict:
    """Read a JSON file and return dictionary payload."""
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON content must be an object: {file_path}")
    return payload


def write_csv_rows(csv_path: Path, header: Sequence[str], rows: Iterable[Sequence]) -> None:
    """Write rows to a CSV file including header."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read all rows from a CSV into list-of-dict format."""
    if not csv_path.exists():
        return []

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def to_relative_path(path: Path, root: Path) -> str:
    """Convert an absolute path to POSIX-style relative path."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def parse_dataset_from_filename(filename: str) -> str:
    """Infer dataset prefix from standardized frame naming."""
    stem = Path(filename).stem
    if "_" not in stem:
        return "unknown"
    return stem.split("_", 1)[0]


def group_id_from_frame_path(frame_path: str) -> str:
    """Derive a leak-proof group ID from standardized frame names."""
    stem = Path(frame_path).stem
    marker = "_f"
    if marker in stem:
        return stem.rsplit(marker, 1)[0]
    return stem


def validate_label_int(label: int) -> bool:
    """Check if label is one of the supported classes."""
    return label in (REAL_LABEL, FAKE_LABEL)


def class_distribution(rows: Sequence[Dict[str, str]]) -> Dict[int, int]:
    """Calculate class counts from row dictionaries containing label field."""
    distribution = {REAL_LABEL: 0, FAKE_LABEL: 0}
    for row in rows:
        try:
            label_value = int(row["label"])
        except Exception:
            continue
        if label_value in distribution:
            distribution[label_value] += 1
    return distribution


def summarize_distribution(distribution: Dict[int, int]) -> str:
    """Format class distribution string for logs and console output."""
    return f"REAL(0)={distribution.get(REAL_LABEL, 0)}, FAKE(1)={distribution.get(FAKE_LABEL, 0)}"
