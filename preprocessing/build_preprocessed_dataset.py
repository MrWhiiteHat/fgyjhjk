"""Main preprocessing pipeline to build model-ready face dataset."""

from __future__ import annotations

import argparse
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

import cv2
from tqdm import tqdm

from align_faces import align_face, crop_face_from_bbox
from deduplicate import DuplicateChecker
from detect_faces import FaceDetector, FaceDetection, select_primary_detection
from normalize import normalize_image, save_tensor
from quality_checks import evaluate_quality
from utils import (
    FAKE_LABEL,
    REAL_LABEL,
    SampleRecord,
    copy_to_rejected,
    ensure_required_output_structure,
    is_supported_media,
    label_to_name,
    load_config,
    load_split_samples,
    now_ms,
    relative_to_dataset_root,
    safe_read_media_frame,
    safe_imwrite,
    save_landmarks_json,
    sample_id_from_record,
    setup_logger,
    stringify_landmarks,
    write_csv_dicts,
)


@dataclass
class ProcessResult:
    """Container for per-sample processing result."""

    accepted_row: Optional[Dict]
    report_row: Dict
    rejected_row: Optional[Dict]


class PreprocessingPipeline:
    """Production preprocessing pipeline for real-vs-fake face data."""

    def __init__(self, config: Dict):
        self.config = config
        ensure_required_output_structure(config)

        self.logger = setup_logger(Path(config["log_file_path"]))
        self.detector = FaceDetector(
            face_detector=config["face_detector"],
            fallback_detector=config.get("fallback_detector", "mtcnn"),
            confidence_threshold=float(config["confidence_threshold"]),
        )

        self.duplicate_checker = DuplicateChecker(hash_threshold=int(config["duplicate_hash_threshold"]))
        self.duplicate_lock = Lock()

        self.accepted_rows: List[Dict] = []
        self.report_rows: List[Dict] = []
        self.rejected_rows: List[Dict] = []

    def run(self) -> None:
        """Execute full preprocessing flow from split CSV files."""
        self.logger.info("Starting preprocessing pipeline")

        samples = load_split_samples(self.config)
        if not samples:
            self.logger.warning("No input samples found in train/val/test CSV files")
            self._write_outputs()
            return

        workers = max(1, int(self.config.get("num_workers", 1)))
        self.logger.info("Loaded %d samples. Running with %d workers", len(samples), workers)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self.process_one, sample) for sample in samples]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Preprocessing"):
                try:
                    result = future.result()
                    self.report_rows.append(result.report_row)
                    if result.accepted_row:
                        self.accepted_rows.append(result.accepted_row)
                    if result.rejected_row:
                        self.rejected_rows.append(result.rejected_row)
                except Exception as exc:
                    self.logger.error("Unhandled worker exception: %s", exc)
                    self.logger.debug(traceback.format_exc())

        self._write_outputs()
        self._print_summary()
        self.logger.info("Completed preprocessing pipeline")

    def process_one(self, sample: SampleRecord) -> ProcessResult:
        """Process one sample through detection, alignment, quality, dedupe, and normalization."""
        started_ms = now_ms()
        sample_id = sample_id_from_record(sample.split, sample.filepath)
        label_name = label_to_name(sample.label)
        source_path = Path("dataset") / sample.filepath
        source_name = Path(sample.filepath).name

        base_report = {
            "sample_id": sample_id,
            "source_filepath": sample.filepath,
            "split": sample.split,
            "label": sample.label,
            "dataset": sample.dataset,
            "status": "rejected",
            "rejection_reason": "",
            "detector": "",
            "confidence": "",
            "num_faces": 0,
            "bbox": "",
            "landmarks": "",
            "blur_score": "",
            "brightness": "",
            "face_hash": "",
            "processing_ms": 0,
            "notes": "",
        }

        if not source_path.exists() or not source_path.is_file():
            reason = "corrupted"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)
            report = dict(base_report)
            report["status"] = "rejected"
            report["rejection_reason"] = reason
            report["notes"] = "Input file missing"
            report["processing_ms"] = now_ms() - started_ms

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": "Input file missing",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        if not is_supported_media(
            source_path,
            allowed_image_extensions=self.config.get("allowed_image_extensions", []),
            allowed_video_extensions=self.config.get("allowed_video_extensions", []),
        ):
            reason = "corrupted"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)

            report = dict(base_report)
            report["rejection_reason"] = reason
            report["notes"] = f"Unsupported media extension: {source_path.suffix.lower()}"
            report["processing_ms"] = now_ms() - started_ms

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": f"Unsupported media extension: {source_path.suffix.lower()}",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        image_bgr = safe_read_media_frame(
            file_path=source_path,
            allowed_image_extensions=self.config.get("allowed_image_extensions", []),
            allowed_video_extensions=self.config.get("allowed_video_extensions", []),
        )
        if image_bgr is None:
            reason = "corrupted"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)
            report = dict(base_report)
            report["rejection_reason"] = reason
            report["notes"] = "Failed to decode image"
            report["processing_ms"] = now_ms() - started_ms

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": "Failed to decode image",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        detections = self.detector.detect(image_bgr)
        primary_detection, reject_reason = select_primary_detection(
            detections=detections,
            min_face_size=int(self.config["min_face_size"]),
            max_faces_allowed=int(self.config["max_faces_allowed"]),
        )

        if reject_reason is not None or primary_detection is None:
            reason = reject_reason or "no_face"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)

            report = dict(base_report)
            report["rejection_reason"] = reason
            report["num_faces"] = len(detections)
            report["processing_ms"] = now_ms() - started_ms
            report["notes"] = "No valid primary face detection"

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": f"detected_faces={len(detections)}",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        face_crop = crop_face_from_bbox(
            image_bgr=image_bgr,
            bbox=primary_detection.bbox,
            margin_ratio=float(self.config.get("face_crop_margin_ratio", 0.2)),
        )

        if face_crop is None or face_crop.size == 0:
            reason = "corrupted"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)

            report = dict(base_report)
            report["rejection_reason"] = reason
            report["detector"] = primary_detection.detector
            report["confidence"] = f"{primary_detection.confidence:.6f}"
            report["num_faces"] = len(detections)
            report["processing_ms"] = now_ms() - started_ms
            report["notes"] = "Face crop is empty"

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": "Empty face crop",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        aligned_face = align_face(
            image_bgr=image_bgr,
            bbox=primary_detection.bbox,
            landmarks=primary_detection.landmarks,
            output_size=(int(self.config["image_size"][0]), int(self.config["image_size"][1])),
            margin_ratio=float(self.config.get("face_crop_margin_ratio", 0.2)),
        )

        quality_ok, quality_reason, quality_metrics = evaluate_quality(
            image_bgr=aligned_face,
            blur_threshold=float(self.config["blur_threshold"]),
            brightness_min=float(self.config["brightness_min"]),
            brightness_max=float(self.config["brightness_max"]),
        )

        if not quality_ok:
            reason = quality_reason
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)

            report = dict(base_report)
            report["rejection_reason"] = reason
            report["detector"] = primary_detection.detector
            report["confidence"] = f"{primary_detection.confidence:.6f}"
            report["num_faces"] = len(detections)
            report["bbox"] = ",".join(f"{v:.2f}" for v in primary_detection.bbox)
            report["landmarks"] = stringify_landmarks(primary_detection.landmarks)
            report["blur_score"] = f"{quality_metrics['blur_score']:.6f}"
            report["brightness"] = f"{quality_metrics['brightness']:.6f}"
            report["processing_ms"] = now_ms() - started_ms
            report["notes"] = "Failed quality checks"

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": f"blur={quality_metrics['blur_score']:.4f};brightness={quality_metrics['brightness']:.4f}",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        with self.duplicate_lock:
            is_duplicate, hash_hex, nearest = self.duplicate_checker.check(sample_id=sample_id, image_bgr=aligned_face)

        if is_duplicate:
            reason = "duplicates"
            rejected_path = self._reject_sample(source_path, reason, sample_id, source_name)

            report = dict(base_report)
            report["rejection_reason"] = reason
            report["detector"] = primary_detection.detector
            report["confidence"] = f"{primary_detection.confidence:.6f}"
            report["num_faces"] = len(detections)
            report["bbox"] = ",".join(f"{v:.2f}" for v in primary_detection.bbox)
            report["landmarks"] = stringify_landmarks(primary_detection.landmarks)
            report["blur_score"] = f"{quality_metrics['blur_score']:.6f}"
            report["brightness"] = f"{quality_metrics['brightness']:.6f}"
            report["face_hash"] = hash_hex
            report["processing_ms"] = now_ms() - started_ms
            report["notes"] = f"duplicate_of={nearest.matched_id if nearest else ''}"

            rejected = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "split": sample.split,
                "label": sample.label,
                "dataset": sample.dataset,
                "rejection_reason": reason,
                "rejected_path": rejected_path,
                "notes": f"hash={hash_hex};duplicate_of={nearest.matched_id if nearest else ''}",
            }
            self.logger.info("Rejected sample_id=%s reason=%s source=%s", sample_id, reason, sample.filepath)
            return ProcessResult(None, report, rejected)

        crop_output_path, landmarks_output_path, preprocessed_output_path, debug_output_path = self._output_paths(
            sample=sample,
            sample_id=sample_id,
            source_name=source_name,
            label_name=label_name,
        )

        safe_imwrite(crop_output_path, face_crop)

        if bool(self.config.get("save_landmarks", True)):
            landmarks_payload = {
                "sample_id": sample_id,
                "source_filepath": sample.filepath,
                "detector": primary_detection.detector,
                "confidence": float(primary_detection.confidence),
                "bbox": [float(v) for v in primary_detection.bbox],
                "landmarks": primary_detection.landmarks,
            }
            save_landmarks_json(landmarks_output_path, landmarks_payload)

        if bool(self.config.get("save_debug_images", True)):
            safe_imwrite(debug_output_path, aligned_face)

        aligned_rgb = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
        normalized_tensor = normalize_image(
            image_rgb=aligned_rgb,
            mean=self.config["normalization_mean"],
            std=self.config["normalization_std"],
        )
        save_tensor(
            preprocessed_output_path,
            normalized_tensor,
            use_fp16=bool(self.config.get("use_fp16_storage", False)),
        )

        report = dict(base_report)
        report["status"] = "accepted"
        report["rejection_reason"] = ""
        report["detector"] = primary_detection.detector
        report["confidence"] = f"{primary_detection.confidence:.6f}"
        report["num_faces"] = len(detections)
        report["bbox"] = ",".join(f"{v:.2f}" for v in primary_detection.bbox)
        report["landmarks"] = stringify_landmarks(primary_detection.landmarks)
        report["blur_score"] = f"{quality_metrics['blur_score']:.6f}"
        report["brightness"] = f"{quality_metrics['brightness']:.6f}"
        report["face_hash"] = hash_hex
        report["processing_ms"] = now_ms() - started_ms
        report["notes"] = ""

        accepted = {
            "sample_id": sample_id,
            "source_filepath": sample.filepath,
            "split": sample.split,
            "label": sample.label,
            "dataset": sample.dataset,
            "face_crop_path": relative_to_dataset_root(crop_output_path),
            "landmarks_path": relative_to_dataset_root(landmarks_output_path) if bool(self.config.get("save_landmarks", True)) else "",
            "preprocessed_path": relative_to_dataset_root(preprocessed_output_path),
            "detector": primary_detection.detector,
            "confidence": f"{primary_detection.confidence:.6f}",
            "bbox": ",".join(f"{v:.2f}" for v in primary_detection.bbox),
            "face_hash": hash_hex,
            "width": int(aligned_face.shape[1]),
            "height": int(aligned_face.shape[0]),
        }

        self.logger.info("Accepted sample_id=%s split=%s label=%s source=%s", sample_id, sample.split, label_name, sample.filepath)

        return ProcessResult(accepted, report, None)

    def _reject_sample(self, source_path: Path, reason: str, sample_id: str, source_name: str) -> str:
        """Copy rejected sample into category-specific folder and return relative path."""
        rejected_root = Path(self.config["rejected_dir"])
        filename = f"{sample_id}_{source_name}"

        try:
            if source_path.exists() and source_path.is_file():
                rejected_path = copy_to_rejected(
                    source_path=source_path,
                    rejected_root=rejected_root,
                    reason=reason,
                    filename=filename,
                )
            else:
                rejected_path = rejected_root / reason / filename
                rejected_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            rejected_path = rejected_root / reason / filename
            rejected_path.parent.mkdir(parents=True, exist_ok=True)

        return relative_to_dataset_root(rejected_path)

    def _output_paths(
        self,
        sample: SampleRecord,
        sample_id: str,
        source_name: str,
        label_name: str,
    ) -> Tuple[Path, Path, Path, Path]:
        """Build all output paths for accepted sample."""
        stem = Path(source_name).stem

        crop_name = f"{sample_id}_{stem}.jpg"
        crop_path = Path(self.config["output_face_crops_dir"]) / label_name / crop_name

        landmarks_name = f"{sample_id}_{stem}.json"
        landmarks_path = Path(self.config["output_landmarks_dir"]) / label_name / landmarks_name

        preprocessed_name = f"{sample_id}_{stem}.npy"
        preprocessed_path = (
            Path(self.config["output_preprocessed_dir"]) / sample.split / label_name / preprocessed_name
        )

        debug_name = f"{sample_id}_{stem}.jpg"
        debug_path = Path(self.config["output_preprocessed_dir"]) / sample.split / label_name / debug_name

        return crop_path, landmarks_path, preprocessed_path, debug_path

    def _write_outputs(self) -> None:
        """Write all output metadata files required by Module 2."""
        accepted_header = [
            "sample_id",
            "source_filepath",
            "split",
            "label",
            "dataset",
            "face_crop_path",
            "landmarks_path",
            "preprocessed_path",
            "detector",
            "confidence",
            "bbox",
            "face_hash",
            "width",
            "height",
        ]

        report_header = [
            "sample_id",
            "source_filepath",
            "split",
            "label",
            "dataset",
            "status",
            "rejection_reason",
            "detector",
            "confidence",
            "num_faces",
            "bbox",
            "landmarks",
            "blur_score",
            "brightness",
            "face_hash",
            "processing_ms",
            "notes",
        ]

        rejected_header = [
            "sample_id",
            "source_filepath",
            "split",
            "label",
            "dataset",
            "rejection_reason",
            "rejected_path",
            "notes",
        ]

        write_csv_dicts(Path(self.config["preprocessed_labels_csv_path"]), self.accepted_rows, accepted_header)
        write_csv_dicts(Path(self.config["preprocessing_report_csv_path"]), self.report_rows, report_header)
        write_csv_dicts(Path(self.config["rejected_samples_csv_path"]), self.rejected_rows, rejected_header)

    def _print_summary(self) -> None:
        """Print and log end-of-run summary for validation and monitoring."""
        accepted = len(self.accepted_rows)
        rejected = len(self.rejected_rows)

        split_counts: Dict[str, int] = {"train": 0, "val": 0, "test": 0}
        class_counts: Dict[str, int] = {"real": 0, "fake": 0}
        for row in self.accepted_rows:
            split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
            class_name = "real" if int(row["label"]) == REAL_LABEL else "fake"
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

        rejection_reason_counts: Dict[str, int] = {}
        for row in self.rejected_rows:
            reason = str(row["rejection_reason"])
            rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1

        self.logger.info("Accepted: %d", accepted)
        self.logger.info("Rejected: %d", rejected)
        self.logger.info(
            "Accepted per split | train=%d val=%d test=%d",
            split_counts.get("train", 0),
            split_counts.get("val", 0),
            split_counts.get("test", 0),
        )
        self.logger.info(
            "Accepted per class | real=%d fake=%d",
            class_counts.get("real", 0),
            class_counts.get("fake", 0),
        )
        self.logger.info("Rejected reasons: %s", rejection_reason_counts)

        print("Preprocessing summary")
        print(f"Accepted: {accepted}")
        print(f"Rejected: {rejected}")
        print(f"Train accepted: {split_counts.get('train', 0)}")
        print(f"Val accepted: {split_counts.get('val', 0)}")
        print(f"Test accepted: {split_counts.get('test', 0)}")
        print(f"Real accepted: {class_counts.get('real', 0)}")
        print(f"Fake accepted: {class_counts.get('fake', 0)}")
        print(f"Rejected reasons: {rejection_reason_counts}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for preprocessing run."""
    parser = argparse.ArgumentParser(description="Build preprocessed face dataset")
    parser.add_argument(
        "--config",
        type=str,
        default="preprocessing/config.yaml",
        help="Path to preprocessing YAML config",
    )
    return parser.parse_args()


def main() -> None:
    """Program entry point."""
    args = parse_args()
    config = load_config(args.config)
    pipeline = PreprocessingPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
