"""Duplicate filtering based on perceptual hashes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class HashMatch:
    """Stores nearest hash match for duplicate diagnostics."""

    matched_id: str
    distance: int


class DuplicateChecker:
    """Incremental duplicate checker using pHash and Hamming distance."""

    def __init__(self, hash_threshold: int = 4) -> None:
        self.hash_threshold = int(hash_threshold)
        self._hashes: Dict[str, np.ndarray] = {}

    @staticmethod
    def compute_phash(image_bgr: np.ndarray) -> np.ndarray:
        """Compute 64-bit perceptual hash vector from image."""
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        dct = cv2.dct(np.float32(resized))
        dct_low = dct[:8, :8]
        median = np.median(dct_low[1:, 1:])
        bits = (dct_low > median).astype(np.uint8).flatten()
        return bits

    @staticmethod
    def hash_to_hex(hash_bits: np.ndarray) -> str:
        """Convert hash bit vector to hex string representation."""
        packed = np.packbits(hash_bits)
        return "".join(f"{int(byte):02x}" for byte in packed)

    @staticmethod
    def hamming_distance(left_bits: np.ndarray, right_bits: np.ndarray) -> int:
        """Compute Hamming distance between two binary hash vectors."""
        return int(np.count_nonzero(left_bits != right_bits))

    def check(self, sample_id: str, image_bgr: np.ndarray) -> Tuple[bool, str, Optional[HashMatch]]:
        """Check if image is duplicate and register hash when unique."""
        current_bits = self.compute_phash(image_bgr)
        current_hex = self.hash_to_hex(current_bits)

        best_match: Optional[HashMatch] = None
        for existing_id, existing_bits in self._hashes.items():
            distance = self.hamming_distance(current_bits, existing_bits)
            if best_match is None or distance < best_match.distance:
                best_match = HashMatch(matched_id=existing_id, distance=distance)
            if distance <= self.hash_threshold:
                return True, current_hex, HashMatch(matched_id=existing_id, distance=distance)

        self._hashes[sample_id] = current_bits
        return False, current_hex, best_match
