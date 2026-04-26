"""Dataset organization and labeling module for deepfake pipeline."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from utils import (  # noqa: E402
    FAKE_LABEL,
    REAL_LABEL,
    copy_with_integrity,
    ensure_required_structure,
    load_config,
    parse_dataset_from_filename,
    read_json_file,
    sanitize_name,
    setup_logger,
    to_relative_path,
    unique_destination_path,
    write_csv_rows,
)


@dataclass
class MediaSample:
    """Container for one media sample discovered in raw datasets."""

    source_path: Path
    dataset: str
    label_name: str
    media_id: str


def is_media_file(file_path: Path, config: Dict) -> bool:
    """Check whether a file is supported video or image format."""
    video_exts = {ext.lower() for ext in config["custom"].get("accepted_video_ext", [])}
    image_exts = {ext.lower() for ext in config["custom"].get("accepted_image_ext", [])}
    return file_path.suffix.lower() in video_exts.union(image_exts)


def collect_faceforensics_samples(config: Dict, logger) -> List[MediaSample]:
    """Collect FaceForensics++ samples and map them to real/fake labels."""
    root = Path(config["paths"]["raw"]["faceforensics"])
    samples: List[MediaSample] = []

    if not root.exists():
        logger.warning("FaceForensics raw directory not found: %s", root)
        return samples

    for file_path in root.rglob("*"):
        if not file_path.is_file() or not is_media_file(file_path, config):
            continue

        rel = file_path.relative_to(root).as_posix().lower()
        if "original_sequences" in rel:
            label_name = "real"
        elif "manipulated_sequences" in rel:
            label_name = "fake"
        else:
            continue

        media_id = sanitize_name(file_path.relative_to(root).with_suffix("").as_posix().replace("/", "_"))
        samples.append(MediaSample(file_path, "faceforensics", label_name, media_id))

    logger.info("FaceForensics samples collected: %d", len(samples))
    return samples


def collect_celebdf_samples(config: Dict, logger) -> List[MediaSample]:
    """Collect Celeb-DF v2 samples from expected folder names."""
    root = Path(config["paths"]["raw"]["celebdf"])
    samples: List[MediaSample] = []

    if not root.exists():
        logger.warning("Celeb-DF raw directory not found: %s", root)
        return samples

    for file_path in root.rglob("*"):
        if not file_path.is_file() or not is_media_file(file_path, config):
            continue

        rel = file_path.relative_to(root).as_posix().lower()
        if "celeb-real" in rel or "youtube-real" in rel:
            label_name = "real"
        elif "celeb-synthesis" in rel or "celeb-fake" in rel or "fake" in rel:
            label_name = "fake"
        else:
            continue

        media_id = sanitize_name(file_path.relative_to(root).with_suffix("").as_posix().replace("/", "_"))
        samples.append(MediaSample(file_path, "celebdf", label_name, media_id))

    logger.info("Celeb-DF samples collected: %d", len(samples))
    return samples


def collect_dfdc_samples(config: Dict, logger) -> List[MediaSample]:
    """Collect DFDC samples using metadata.json labels when available."""
    root = Path(config["paths"]["raw"]["dfdc"])
    samples: List[MediaSample] = []

    if not root.exists():
        logger.warning("DFDC raw directory not found: %s", root)
        return samples

    metadata_files = sorted(root.rglob("metadata.json"))
    indexed_files = set()

    for metadata_file in metadata_files:
        try:
            payload = read_json_file(metadata_file)
        except Exception as exc:
            logger.error("Failed to parse metadata file %s: %s", metadata_file, exc)
            continue

        for video_name, details in payload.items():
            source_file = metadata_file.parent / video_name
            if not source_file.exists():
                logger.warning("DFDC metadata points to missing file: %s", source_file)
                continue
            if not is_media_file(source_file, config):
                continue

            label_text = str(details.get("label", "")).upper()
            label_name = "fake" if label_text == "FAKE" else "real"
            media_id = sanitize_name(f"{metadata_file.parent.name}_{Path(video_name).stem}")
            samples.append(MediaSample(source_file, "dfdc", label_name, media_id))
            indexed_files.add(source_file.resolve())

    # Fallback scan for files that were not listed in metadata.
    for file_path in root.rglob("*"):
        if not file_path.is_file() or not is_media_file(file_path, config):
            continue
        if file_path.resolve() in indexed_files:
            continue

        rel = file_path.relative_to(root).as_posix().lower()
        if "fake" in rel:
            label_name = "fake"
        elif "real" in rel:
            label_name = "real"
        else:
            logger.warning("Skipping unlabeled DFDC file without metadata: %s", file_path)
            continue

        media_id = sanitize_name(file_path.relative_to(root).with_suffix("").as_posix().replace("/", "_"))
        samples.append(MediaSample(file_path, "dfdc", label_name, media_id))

    logger.info("DFDC samples collected: %d", len(samples))
    return samples


def parse_custom_label(value: str) -> Optional[str]:
    """Map custom label values to canonical real/fake names."""
    normalized = str(value).strip().lower()
    if normalized in {"0", "real", "r"}:
        return "real"
    if normalized in {"1", "fake", "f"}:
        return "fake"
    return None


def collect_custom_samples(config: Dict, logger) -> List[MediaSample]:
    """Collect custom samples from folder-based or CSV-based labels."""
    root = Path(config["paths"]["raw"]["custom"])
    samples: List[MediaSample] = []
    seen = set()

    if not root.exists():
        logger.warning("Custom raw directory not found: %s", root)
        return samples

    # Folder-based convention: custom/real/* and custom/fake/*
    for label_name in ("real", "fake"):
        label_dir = root / label_name
        if not label_dir.exists():
            continue
        for file_path in label_dir.rglob("*"):
            if not file_path.is_file() or not is_media_file(file_path, config):
                continue
            media_id = sanitize_name(file_path.relative_to(root).with_suffix("").as_posix().replace("/", "_"))
            sample = MediaSample(file_path, "custom", label_name, media_id)
            samples.append(sample)
            seen.add(file_path.resolve())

    # Optional CSV convention: custom/labels.csv with columns filepath,label
    csv_path = root / "labels.csv"
    if csv_path.exists():
        try:
            with csv_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    raw_file = str(row.get("filepath", "")).strip()
                    raw_label = str(row.get("label", "")).strip()
                    if not raw_file:
                        continue

                    file_path = Path(raw_file)
                    if not file_path.is_absolute():
                        file_path = root / file_path
                    if not file_path.exists() or not file_path.is_file():
                        logger.warning("Custom labels.csv missing file: %s", file_path)
                        continue
                    if not is_media_file(file_path, config):
                        logger.warning("Custom labels.csv unsupported format: %s", file_path)
                        continue
                    if file_path.resolve() in seen:
                        continue

                    parsed_label = parse_custom_label(raw_label)
                    if parsed_label is None:
                        logger.warning("Invalid custom label '%s' for file: %s", raw_label, file_path)
                        continue

                    media_id = sanitize_name(file_path.relative_to(root).with_suffix("").as_posix().replace("/", "_"))
                    sample = MediaSample(file_path, "custom", parsed_label, media_id)
                    samples.append(sample)
                    seen.add(file_path.resolve())
        except Exception as exc:
            logger.error("Failed reading custom labels.csv: %s", exc)

    logger.info("Custom samples collected: %d", len(samples))
    return samples


def copy_samples_to_processed(samples: List[MediaSample], config: Dict, logger, overwrite: bool) -> Dict[str, int]:
    """Copy collected samples into dataset/processed/{real,fake} folders."""
    processed_real = Path(config["paths"]["processed"]["real"])
    processed_fake = Path(config["paths"]["processed"]["fake"])

    stats = {"copied": 0, "skipped": 0, "errors": 0}

    for sample in samples:
        try:
            target_root = processed_real if sample.label_name == "real" else processed_fake
            filename = f"{sanitize_name(sample.dataset)}_{sanitize_name(sample.media_id)}{sample.source_path.suffix.lower()}"
            destination = unique_destination_path(target_root, filename)

            if destination.exists() and not overwrite:
                stats["skipped"] += 1
                logger.info("Skipped existing processed file: %s", destination)
                continue

            copy_with_integrity(sample.source_path, destination, overwrite=overwrite)
            stats["copied"] += 1
            logger.info("Processed file copied: %s -> %s", sample.source_path, destination)
        except Exception as exc:
            stats["errors"] += 1
            logger.error("Failed to copy sample %s: %s", sample.source_path, exc)

    return stats


def build_labels_from_frames(config: Dict, logger) -> Dict[str, int]:
    """Create metadata/labels.csv from extracted frame folders."""
    dataset_root = Path(config["paths"]["root"])
    frames_real = Path(config["paths"]["frames"]["real"])
    frames_fake = Path(config["paths"]["frames"]["fake"])
    labels_csv = Path(config["paths"]["metadata"]["labels"])

    image_exts = {ext.lower() for ext in config["custom"].get("accepted_image_ext", [])}

    rows = []
    real_count = 0
    fake_count = 0

    for label_name, label_int, folder in (
        ("real", REAL_LABEL, frames_real),
        ("fake", FAKE_LABEL, frames_fake),
    ):
        if not folder.exists():
            logger.warning("Frame folder missing: %s", folder)
            continue

        for frame_file in sorted(folder.rglob("*")):
            if not frame_file.is_file() or frame_file.suffix.lower() not in image_exts:
                continue

            dataset_key = parse_dataset_from_filename(frame_file.name)
            relative_path = to_relative_path(frame_file, dataset_root)
            rows.append((relative_path, label_int, dataset_key))

            if label_name == "real":
                real_count += 1
            else:
                fake_count += 1

    rows.sort(key=lambda item: item[0])
    write_csv_rows(labels_csv, ["filepath", "label", "dataset"], rows)
    logger.info("labels.csv generated at %s with %d rows", labels_csv, len(rows))

    return {"real": real_count, "fake": fake_count, "total": len(rows)}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for organization and labeling actions."""
    parser = argparse.ArgumentParser(description="Organize datasets and build labels")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--action",
        type=str,
        default="all",
        choices=["organize", "label", "all"],
        help="Action to execute",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite already copied processed files",
    )
    return parser.parse_args()


def main() -> None:
    """Run dataset organization and/or frame labeling workflow."""
    args = parse_args()
    config = load_config(args.config)
    ensure_required_structure(config)

    logger = setup_logger(Path(config["paths"]["logs"]["pipeline"]))
    logger.info("Starting labeling module with action=%s", args.action)

    if args.action in {"organize", "all"}:
        all_samples: List[MediaSample] = []
        all_samples.extend(collect_faceforensics_samples(config, logger))
        all_samples.extend(collect_celebdf_samples(config, logger))
        all_samples.extend(collect_dfdc_samples(config, logger))
        all_samples.extend(collect_custom_samples(config, logger))

        copy_stats = copy_samples_to_processed(all_samples, config, logger, overwrite=args.overwrite)
        logger.info(
            "Organization complete | copied=%d skipped=%d errors=%d",
            copy_stats["copied"],
            copy_stats["skipped"],
            copy_stats["errors"],
        )
        print("Organization summary")
        print(f"Copied: {copy_stats['copied']}")
        print(f"Skipped: {copy_stats['skipped']}")
        print(f"Errors: {copy_stats['errors']}")

    if args.action in {"label", "all"}:
        label_stats = build_labels_from_frames(config, logger)
        print("Labeling summary")
        print(f"Total Real: {label_stats['real']}")
        print(f"Total Fake: {label_stats['fake']}")
        print(f"Total Frames: {label_stats['total']}")

    logger.info("Completed labeling module")


if __name__ == "__main__":
    main()
