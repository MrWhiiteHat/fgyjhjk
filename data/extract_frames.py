"""Frame extraction module for deepfake data pipeline."""

from __future__ import annotations

import argparse
import hashlib
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

import cv2
from tqdm import tqdm

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from utils import (  # noqa: E402
    ensure_required_structure,
    load_config,
    sanitize_name,
    setup_logger,
)


def infer_dataset_from_processed_file(file_path: Path) -> str:
    """Infer dataset key from standardized processed filename."""
    stem = file_path.stem
    if "_" not in stem:
        return "custom"
    return stem.split("_", 1)[0]


def clear_existing_frames(frames_dir: Path, logger) -> None:
    """Delete old frame files to guarantee clean extraction runs."""
    removed = 0
    for file_path in frames_dir.rglob("*"):
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
            removed += 1
    logger.info("Cleared %d existing frame files from %s", removed, frames_dir)


def collect_extraction_tasks(config: Dict, logger) -> List[Dict]:
    """Build extraction tasks from processed real/fake folders."""
    tasks: List[Dict] = []
    processed_real = Path(config["paths"]["processed"]["real"])
    processed_fake = Path(config["paths"]["processed"]["fake"])

    video_exts = {ext.lower() for ext in config["custom"].get("accepted_video_ext", [])}
    image_exts = {ext.lower() for ext in config["custom"].get("accepted_image_ext", [])}

    for label_name, source_dir in (("real", processed_real), ("fake", processed_fake)):
        if not source_dir.exists():
            logger.warning("Processed folder missing: %s", source_dir)
            continue

        for media_path in source_dir.rglob("*"):
            if not media_path.is_file():
                continue

            suffix = media_path.suffix.lower()
            if suffix not in video_exts and suffix not in image_exts:
                logger.info("Skipping unsupported format: %s", media_path)
                continue

            tasks.append(
                {
                    "source": str(media_path),
                    "label_name": label_name,
                    "dataset": infer_dataset_from_processed_file(media_path),
                    "target_dir": config["paths"]["frames"][label_name],
                    "target_fps": float(config["processing"].get("fps", 5)),
                    "image_size": config["processing"].get("image_size", [224, 224]),
                    "jpeg_quality": int(config["processing"].get("jpeg_quality", 95)),
                    "deduplicate": bool(config["processing"].get("deduplicate_frames", True)),
                    "video_exts": list(video_exts),
                    "image_exts": list(image_exts),
                }
            )

    logger.info("Collected %d extraction tasks", len(tasks))
    return tasks


def resize_if_needed(frame, image_size: List[int]):
    """Resize frame to configured dimensions."""
    if not image_size or len(image_size) != 2:
        return frame
    width = int(image_size[0])
    height = int(image_size[1])
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def save_encoded_frame(frame, output_file: Path, jpeg_quality: int) -> bool:
    """Encode and save a frame using JPEG format."""
    success, encoded = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, jpeg_quality))],
    )
    if not success:
        return False

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as handle:
        handle.write(encoded.tobytes())
    return True


def extract_from_image(task: Dict) -> Dict:
    """Handle image input by converting one image to one standardized frame."""
    source_path = Path(task["source"])
    target_dir = Path(task["target_dir"])
    dataset = sanitize_name(task["dataset"])
    video_id = sanitize_name(source_path.stem)

    frame = cv2.imread(str(source_path))
    if frame is None or frame.size == 0:
        return {
            "saved": 0,
            "errors": 1,
            "skipped": 1,
            "duplicates": 0,
            "message": f"Corrupted image skipped: {source_path}",
        }

    frame = resize_if_needed(frame, task["image_size"])
    output_file = target_dir / f"{dataset}_{video_id}_f000000.jpg"

    if output_file.exists():
        return {
            "saved": 0,
            "errors": 0,
            "skipped": 1,
            "duplicates": 1,
            "message": f"Duplicate frame target skipped: {output_file}",
        }

    if not save_encoded_frame(frame, output_file, task["jpeg_quality"]):
        return {
            "saved": 0,
            "errors": 1,
            "skipped": 1,
            "duplicates": 0,
            "message": f"Failed to encode image: {source_path}",
        }

    return {
        "saved": 1,
        "errors": 0,
        "skipped": 0,
        "duplicates": 0,
        "message": f"Processed image: {source_path}",
    }


def extract_from_video(task: Dict) -> Dict:
    """Extract deduplicated frames from a video at configured FPS."""
    source_path = Path(task["source"])
    target_dir = Path(task["target_dir"])
    dataset = sanitize_name(task["dataset"])
    video_id = sanitize_name(source_path.stem)

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        return {
            "saved": 0,
            "errors": 1,
            "skipped": 1,
            "duplicates": 0,
            "message": f"Corrupted video skipped: {source_path}",
        }

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    if source_fps <= 0:
        source_fps = float(task["target_fps"])

    step = max(1, int(round(source_fps / max(1.0, float(task["target_fps"])))) )

    saved = 0
    errors = 0
    skipped = 0
    duplicates = 0
    frame_idx = 0
    seen_hashes = set()

    while True:
        success, frame = capture.read()
        if not success:
            break

        if frame_idx % step != 0:
            frame_idx += 1
            continue

        if frame is None or frame.size == 0:
            skipped += 1
            frame_idx += 1
            continue

        frame = resize_if_needed(frame, task["image_size"])
        encoded_ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, task["jpeg_quality"]))],
        )
        if not encoded_ok:
            errors += 1
            frame_idx += 1
            continue

        if task["deduplicate"]:
            frame_hash = hashlib.md5(encoded.tobytes()).hexdigest()
            if frame_hash in seen_hashes:
                duplicates += 1
                frame_idx += 1
                continue
            seen_hashes.add(frame_hash)

        output_name = f"{dataset}_{video_id}_f{saved:06d}.jpg"
        output_path = target_dir / output_name
        if output_path.exists():
            duplicates += 1
            frame_idx += 1
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as handle:
            handle.write(encoded.tobytes())
        saved += 1
        frame_idx += 1

    capture.release()

    if saved == 0:
        return {
            "saved": 0,
            "errors": errors + 1,
            "skipped": skipped,
            "duplicates": duplicates,
            "message": f"No valid frames extracted from: {source_path}",
        }

    return {
        "saved": saved,
        "errors": errors,
        "skipped": skipped,
        "duplicates": duplicates,
        "message": f"Processed video: {source_path}",
    }


def extraction_worker(task: Dict) -> Dict:
    """Dispatch extraction based on media type."""
    source_path = Path(task["source"])
    suffix = source_path.suffix.lower()
    if suffix in set(task["image_exts"]):
        return extract_from_image(task)
    return extract_from_video(task)


def parse_args() -> argparse.Namespace:
    """Parse extraction command-line arguments."""
    parser = argparse.ArgumentParser(description="Extract frames from processed media")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--workers", type=int, default=0, help="Process count (0 uses config value)")
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Remove existing frames before extraction",
    )
    return parser.parse_args()


def main() -> None:
    """Run frame extraction over processed datasets."""
    args = parse_args()
    config = load_config(args.config)
    ensure_required_structure(config)

    logger = setup_logger(Path(config["paths"]["logs"]["pipeline"]))
    logger.info("Starting frame extraction module")

    if args.clear_output:
        clear_existing_frames(Path(config["paths"]["frames"]["real"]), logger)
        clear_existing_frames(Path(config["paths"]["frames"]["fake"]), logger)

    tasks = collect_extraction_tasks(config, logger)
    if not tasks:
        logger.warning("No processed media files found for extraction")
        print("No files found in dataset/processed/{real,fake}")
        return

    workers = args.workers if args.workers > 0 else int(config["download"].get("num_workers", 4))
    workers = max(1, workers)

    totals = {"saved": 0, "errors": 0, "skipped": 0, "duplicates": 0}

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(extraction_worker, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Extracting frames"):
            try:
                result = future.result()
                totals["saved"] += int(result.get("saved", 0))
                totals["errors"] += int(result.get("errors", 0))
                totals["skipped"] += int(result.get("skipped", 0))
                totals["duplicates"] += int(result.get("duplicates", 0))
                logger.info(result.get("message", "Extraction task finished"))
            except Exception as exc:
                totals["errors"] += 1
                logger.error("Extraction worker failed: %s", exc)

    logger.info(
        "Frame extraction done | saved=%d skipped=%d duplicates=%d errors=%d",
        totals["saved"],
        totals["skipped"],
        totals["duplicates"],
        totals["errors"],
    )

    print("Frame extraction summary")
    print(f"Saved: {totals['saved']}")
    print(f"Skipped: {totals['skipped']}")
    print(f"Duplicates: {totals['duplicates']}")
    print(f"Errors: {totals['errors']}")


if __name__ == "__main__":
    main()
