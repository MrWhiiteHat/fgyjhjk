"""Video frame sampling for edge video inference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np


@dataclass
class SampledFrame:
    """Represents one sampled video frame."""

    frame_index: int
    timestamp_sec: float
    rgb: np.ndarray


def sample_video_frames(
    video_path: str | Path,
    max_frames: int = 32,
    frame_stride: int = 5,
) -> list[SampledFrame]:
    """Sample RGB frames from video file with stride and cap."""
    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")
    if path.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise ValueError(f"Unsupported video extension: {path.suffix.lower()}")

    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Unable to decode video: {path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 25.0

    stride = max(1, int(frame_stride))
    limit = max(1, int(max_frames))

    sampled: list[SampledFrame] = []
    frame_idx = 0
    try:
        while len(sampled) < limit:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            if frame_idx % stride == 0:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                sampled.append(
                    SampledFrame(
                        frame_index=frame_idx,
                        timestamp_sec=frame_idx / fps,
                        rgb=frame_rgb,
                    )
                )
            frame_idx += 1
    finally:
        cap.release()

    return sampled
