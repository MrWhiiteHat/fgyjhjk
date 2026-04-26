"""Face detection module with RetinaFace primary and MTCNN fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np


@dataclass
class FaceDetection:
    """Represents one detected face and its metadata."""

    bbox: Tuple[float, float, float, float]
    confidence: float
    landmarks: Dict[str, Tuple[float, float]]
    detector: str


class FaceDetector:
    """Unified face detector using RetinaFace as primary and MTCNN as fallback."""

    def __init__(
        self,
        face_detector: str = "retinaface",
        fallback_detector: str = "mtcnn",
        confidence_threshold: float = 0.9,
    ) -> None:
        self.face_detector = str(face_detector).strip().lower()
        self.fallback_detector = str(fallback_detector).strip().lower()
        self.confidence_threshold = float(confidence_threshold)

        self._retinaface = None
        self._mtcnn = None
        self._opencv_cascade = None

    def _load_retinaface(self):
        """Lazy-load RetinaFace detector implementation."""
        if self._retinaface is not None:
            return self._retinaface

        try:
            from retinaface import RetinaFace  # type: ignore

            self._retinaface = RetinaFace
        except Exception:
            self._retinaface = None
        return self._retinaface

    def _load_mtcnn(self):
        """Lazy-load MTCNN detector implementation."""
        if self._mtcnn is not None:
            return self._mtcnn

        try:
            from mtcnn import MTCNN  # type: ignore

            self._mtcnn = MTCNN()
        except Exception:
            self._mtcnn = None
        return self._mtcnn

    def _load_opencv_haar(self):
        """Load OpenCV Haar cascade as safety fallback when deep models are unavailable."""
        if self._opencv_cascade is not None:
            return self._opencv_cascade

        try:
            model_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(model_path)
            if cascade.empty():
                self._opencv_cascade = None
            else:
                self._opencv_cascade = cascade
        except Exception:
            self._opencv_cascade = None
        return self._opencv_cascade

    def detect(self, image_bgr: np.ndarray) -> List[FaceDetection]:
        """Detect faces and return filtered detections sorted by confidence."""
        detections: List[FaceDetection] = []
        preferred = self.face_detector

        if preferred == "retinaface":
            detections = self._detect_with_retinaface(image_bgr)
            if not detections:
                detections = self._detect_with_fallback(image_bgr)
        elif preferred == "mtcnn":
            detections = self._detect_with_mtcnn(image_bgr)
            if not detections:
                detections = self._detect_with_fallback(image_bgr)
        else:
            detections = self._detect_with_retinaface(image_bgr)
            if not detections:
                detections = self._detect_with_fallback(image_bgr)

        filtered = [det for det in detections if float(det.confidence) >= self.confidence_threshold]
        filtered.sort(key=lambda item: (item.confidence, self._bbox_area(item.bbox)), reverse=True)
        return filtered

    def _detect_with_fallback(self, image_bgr: np.ndarray) -> List[FaceDetection]:
        """Apply configured fallback detector, then final OpenCV fallback."""
        if self.fallback_detector == "mtcnn":
            fallback = self._detect_with_mtcnn(image_bgr)
        elif self.fallback_detector == "retinaface":
            fallback = self._detect_with_retinaface(image_bgr)
        else:
            fallback = []

        if fallback:
            return fallback
        return self._detect_with_haar(image_bgr)

    def _detect_with_retinaface(self, image_bgr: np.ndarray) -> List[FaceDetection]:
        """Detect faces using RetinaFace package output."""
        model = self._load_retinaface()
        if model is None:
            return []

        try:
            outputs = model.detect_faces(image_bgr)
        except Exception:
            return []

        if not outputs:
            return []

        detections: List[FaceDetection] = []
        if isinstance(outputs, dict):
            for payload in outputs.values():
                bbox = payload.get("facial_area", None)
                score = payload.get("score", 0.0)
                landmarks = payload.get("landmarks", {}) or {}
                if not bbox or len(bbox) != 4:
                    continue
                parsed_landmarks = self._normalize_landmarks(landmarks)
                detections.append(
                    FaceDetection(
                        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                        confidence=float(score),
                        landmarks=parsed_landmarks,
                        detector="retinaface",
                    )
                )
        return detections

    def _detect_with_mtcnn(self, image_bgr: np.ndarray) -> List[FaceDetection]:
        """Detect faces using MTCNN package output."""
        model = self._load_mtcnn()
        if model is None:
            return []

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        try:
            outputs = model.detect_faces(image_rgb)
        except Exception:
            return []

        detections: List[FaceDetection] = []
        for payload in outputs:
            bbox = payload.get("box", None)
            confidence = payload.get("confidence", 0.0)
            keypoints = payload.get("keypoints", {}) or {}

            if not bbox or len(bbox) != 4:
                continue
            x, y, w, h = bbox
            x1 = float(x)
            y1 = float(y)
            x2 = float(x + w)
            y2 = float(y + h)

            parsed_landmarks = self._normalize_landmarks(keypoints)
            detections.append(
                FaceDetection(
                    bbox=(x1, y1, x2, y2),
                    confidence=float(confidence),
                    landmarks=parsed_landmarks,
                    detector="mtcnn",
                )
            )

        return detections

    def _detect_with_haar(self, image_bgr: np.ndarray) -> List[FaceDetection]:
        """Detect faces with Haar cascade as last-resort fallback."""
        cascade = self._load_opencv_haar()
        if cascade is None:
            return []

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        detections: List[FaceDetection] = []

        for (x, y, w, h) in faces:
            detections.append(
                FaceDetection(
                    bbox=(float(x), float(y), float(x + w), float(y + h)),
                    confidence=0.95,
                    landmarks={},
                    detector="opencv_haar_fallback",
                )
            )
        return detections

    @staticmethod
    def _bbox_area(bbox: Sequence[float]) -> float:
        """Calculate bounding box area."""
        x1, y1, x2, y2 = [float(v) for v in bbox]
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @staticmethod
    def _normalize_landmarks(raw: Dict) -> Dict[str, Tuple[float, float]]:
        """Normalize landmark dictionary across detector outputs."""
        output: Dict[str, Tuple[float, float]] = {}

        mapping = {
            "left_eye": "left_eye",
            "right_eye": "right_eye",
            "nose": "nose",
            "mouth_left": "mouth_left",
            "mouth_right": "mouth_right",
        }

        for input_key, canonical_key in mapping.items():
            if input_key not in raw:
                continue
            value = raw.get(input_key)
            if not value or len(value) != 2:
                continue
            output[canonical_key] = (float(value[0]), float(value[1]))

        return output


def select_primary_detection(
    detections: List[FaceDetection],
    min_face_size: int,
    max_faces_allowed: int,
) -> Tuple[Optional[FaceDetection], Optional[str]]:
    """Select best face detection and return rejection reason when invalid."""
    if not detections:
        return None, "no_face"

    if len(detections) > int(max_faces_allowed):
        return None, "multi_face"

    best = detections[0]
    x1, y1, x2, y2 = best.bbox
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    if width < float(min_face_size) or height < float(min_face_size):
        return None, "no_face"

    return best, None
