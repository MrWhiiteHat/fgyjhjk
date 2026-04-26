"""Sampler helpers for class-imbalance handling."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import torch
from torch.utils.data import WeightedRandomSampler

from training.data.dataset import FaceBinaryDataset


def get_class_counts(dataset: FaceBinaryDataset) -> Dict[int, int]:
    """Get per-class sample counts for dataset."""
    labels = dataset.labels()
    return {0: labels.count(0), 1: labels.count(1)}


def create_weighted_sampler(
    dataset: FaceBinaryDataset,
    class_weights: Optional[list[float]],
    replacement: bool,
    logger: logging.Logger,
) -> Optional[WeightedRandomSampler]:
    """Create WeightedRandomSampler to improve class exposure in imbalanced training."""
    labels = dataset.labels()
    if len(labels) == 0:
        logger.warning("Sampler not created because dataset is empty")
        return None

    counts = get_class_counts(dataset)
    if counts[0] == 0 or counts[1] == 0:
        logger.warning("Sampler disabled because one class is empty: %s", counts)
        return None

    # Base inverse-frequency weighting.
    base_weights = {
        0: 1.0 / counts[0],
        1: 1.0 / counts[1],
    }

    if class_weights and len(class_weights) == 2:
        # Multiplicative scaling gives manual class-priority control.
        base_weights[0] *= float(class_weights[0])
        base_weights[1] *= float(class_weights[1])

    weights = [base_weights[int(label)] for label in labels]
    sampler = WeightedRandomSampler(
        weights=torch.tensor(weights, dtype=torch.double),
        num_samples=len(weights),
        replacement=bool(replacement),
    )

    logger.info(
        "Created WeightedRandomSampler | counts=%s base_weights=%s replacement=%s",
        counts,
        base_weights,
        replacement,
    )
    logger.info(
        "Imbalance note: sampler helps exposure; weighted loss helps objective scaling; "
        "using both together can over-correct heavily imbalanced data."
    )
    return sampler
