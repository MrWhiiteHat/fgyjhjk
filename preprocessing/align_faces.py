"""Face crop and alignment utilities."""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

from utils import clamp_bbox


def crop_face_from_bbox(
    image_bgr: np.ndarray,
    bbox: Sequence[float],
    margin_ratio: float = 0.2,
) -> np.ndarray:
    """Crop a face region from image using bbox and optional margin expansion."""
    x1, y1, x2, y2 = clamp_bbox(bbox, image_bgr.shape, margin_ratio=margin_ratio)
    face = image_bgr[y1:y2, x1:x2]
    if face is None or face.size == 0:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return face


def _compute_eye_based_transform(
    landmarks: Dict[str, Tuple[float, float]],
    output_size: Tuple[int, int],
) -> Optional[np.ndarray]:
    """Compute affine transform matrix from eyes and nose landmarks."""
    if "left_eye" not in landmarks or "right_eye" not in landmarks:
        return None

    left_eye = np.array(landmarks["left_eye"], dtype=np.float32)
    right_eye = np.array(landmarks["right_eye"], dtype=np.float32)

    if np.linalg.norm(left_eye - right_eye) < 1e-3:
        return None

    # Canonical target coordinates for frontal face alignment.
    width, height = int(output_size[0]), int(output_size[1])
    target_left_eye = np.array([0.35 * width, 0.38 * height], dtype=np.float32)
    target_right_eye = np.array([0.65 * width, 0.38 * height], dtype=np.float32)

    if "nose" in landmarks:
        source_nose = np.array(landmarks["nose"], dtype=np.float32)
    else:
        source_nose = (left_eye + right_eye) / 2.0 + np.array([0.0, 20.0], dtype=np.float32)

    target_nose = np.array([0.5 * width, 0.56 * height], dtype=np.float32)

    src = np.vstack([left_eye, right_eye, source_nose]).astype(np.float32)
    dst = np.vstack([target_left_eye, target_right_eye, target_nose]).astype(np.float32)
    matrix = cv2.getAffineTransform(src, dst)
    return matrix


def align_face(
    image_bgr: np.ndarray,
    bbox: Sequence[float],
    landmarks: Optional[Dict[str, Tuple[float, float]]],
    output_size: Tuple[int, int],
    margin_ratio: float = 0.2,
) -> np.ndarray:
    """Align face using landmarks when available, otherwise fallback to bbox crop resize."""
    width, height = int(output_size[0]), int(output_size[1])

    if landmarks:
        matrix = _compute_eye_based_transform(landmarks, output_size=(width, height))
        if matrix is not None:
            aligned = cv2.warpAffine(
                image_bgr,
                matrix,
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )
            if aligned is not None and aligned.size > 0:
                return aligned

    cropped = crop_face_from_bbox(image_bgr, bbox, margin_ratio=margin_ratio)
    aligned = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_AREA)
    return aligned
