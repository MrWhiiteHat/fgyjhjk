"""Dataset loading for binary real-vs-fake face classification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset

from training.utils.helpers import check_split_leakage, compute_class_distribution


LABEL_MAP = {"real": 0, "fake": 1}


@dataclass
class SampleItem:
    """Container for one dataset sample."""

    filepath: Path
    label: int
    split: str
    metadata: Dict


class FaceBinaryDataset(Dataset):
    """Robust dataset for loading samples from directory structure or metadata CSV."""

    def __init__(
        self,
        split: str,
        split_dir: Path,
        transform,
        metadata_csv: Optional[Path],
        allowed_image_extensions: Sequence[str],
        allowed_array_extensions: Sequence[str],
        logger: logging.Logger,
    ) -> None:
        self.split = split
        self.split_dir = split_dir
        self.transform = transform
        self.metadata_csv = metadata_csv
        self.allowed_image_extensions = {ext.lower() for ext in allowed_image_extensions}
        self.allowed_array_extensions = {ext.lower() for ext in allowed_array_extensions}
        self.logger = logger

        self.samples: List[SampleItem] = []
        self.skipped: List[Dict] = []

        self._index_samples()
        self.class_counts = compute_class_distribution([sample.label for sample in self.samples])

    def _index_samples(self) -> None:
        """Build sample index from CSV when available, otherwise from directory tree."""
        collected: List[SampleItem] = []

        if self.metadata_csv and self.metadata_csv.exists():
            csv_samples = self._collect_from_csv(self.metadata_csv)
            if csv_samples:
                collected.extend(csv_samples)

        if not collected:
            dir_samples = self._collect_from_directory()
            collected.extend(dir_samples)

        for sample in collected:
            if not sample.filepath.exists() or not sample.filepath.is_file():
                self.skipped.append({"filepath": str(sample.filepath), "reason": "missing_file"})
                continue

            if not self._is_allowed_extension(sample.filepath):
                self.skipped.append({"filepath": str(sample.filepath), "reason": "wrong_extension"})
                continue

            if not self._is_readable(sample.filepath):
                self.skipped.append({"filepath": str(sample.filepath), "reason": "unreadable"})
                continue

            self.samples.append(sample)

        self.logger.info(
            "Indexed split=%s | valid=%d skipped=%d",
            self.split,
            len(self.samples),
            len(self.skipped),
        )

    def _collect_from_directory(self) -> List[SampleItem]:
        """Collect samples directly from split directory real/fake subfolders."""
        items: List[SampleItem] = []
        if not self.split_dir.exists():
            self.logger.warning("Split directory missing: %s", self.split_dir)
            return items

        for class_name, label in LABEL_MAP.items():
            class_dir = self.split_dir / class_name
            if not class_dir.exists():
                self.logger.warning("Class directory missing for split '%s': %s", self.split, class_dir)
                continue

            for file_path in sorted(class_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                item = SampleItem(
                    filepath=file_path,
                    label=int(label),
                    split=self.split,
                    metadata={"source": "directory"},
                )
                items.append(item)

        return self._prefer_array_over_image(items)

    def _collect_from_csv(self, metadata_csv: Path) -> List[SampleItem]:
        """Collect samples from metadata CSV with split filtering."""
        items: List[SampleItem] = []

        try:
            table = pd.read_csv(metadata_csv)
        except Exception as exc:
            self.logger.error("Failed to read metadata CSV %s: %s", metadata_csv, exc)
            return items

        if table.empty:
            return items

        has_split = "split" in table.columns
        has_preprocessed_path = "preprocessed_path" in table.columns

        if not has_preprocessed_path:
            return items

        for _, row in table.iterrows():
            row_split = str(row.get("split", "")).strip().lower() if has_split else ""
            if has_split and row_split != self.split:
                continue

            raw_path = str(row.get("preprocessed_path", "")).strip()
            if not raw_path:
                continue

            path = Path(raw_path)
            if not path.is_absolute():
                path_str = path.as_posix()
                if path_str.startswith("dataset/"):
                    path = Path(path_str)
                else:
                    path = Path("dataset") / path

            label_value = row.get("label", row.get("true_label", None))
            try:
                label_int = int(label_value)
            except Exception:
                text_value = str(label_value).strip().lower()
                label_int = LABEL_MAP.get(text_value, -1)

            if label_int not in (0, 1):
                self.skipped.append({"filepath": str(path), "reason": "invalid_label"})
                continue

            metadata = {k: row[k] for k in table.columns if k in row and k not in {"preprocessed_path"}}
            items.append(SampleItem(filepath=path, label=label_int, split=self.split, metadata=metadata))

        return self._prefer_array_over_image(items)

    def _prefer_array_over_image(self, items: Sequence[SampleItem]) -> List[SampleItem]:
        """Prefer NPY arrays over image files when both share same stem path."""
        best_by_stem: Dict[str, SampleItem] = {}

        def rank(path: Path) -> int:
            suffix = path.suffix.lower()
            if suffix in self.allowed_array_extensions:
                return 0
            if suffix in self.allowed_image_extensions:
                return 1
            return 2

        for item in items:
            key = str(item.filepath.with_suffix(""))
            current = best_by_stem.get(key)
            if current is None or rank(item.filepath) < rank(current.filepath):
                best_by_stem[key] = item

        return list(best_by_stem.values())

    def _is_allowed_extension(self, path: Path) -> bool:
        """Validate file extension against configured image/array extensions."""
        suffix = path.suffix.lower()
        return suffix in self.allowed_image_extensions or suffix in self.allowed_array_extensions

    def _is_readable(self, path: Path) -> bool:
        """Quickly check whether image or numpy array can be opened."""
        suffix = path.suffix.lower()
        try:
            if suffix in self.allowed_array_extensions:
                _ = np.load(path, allow_pickle=False, mmap_mode="r")
                return True
            if suffix in self.allowed_image_extensions:
                with Image.open(path) as image:
                    image.verify()
                return True
            return False
        except Exception:
            return False

    def __len__(self) -> int:
        """Return total number of valid indexed samples."""
        return len(self.samples)

    def __getitem__(self, index: int) -> Dict:
        """Load one sample and return tensor, label, filepath, and metadata."""
        sample = self.samples[index]
        suffix = sample.filepath.suffix.lower()

        if suffix in self.allowed_array_extensions:
            image_tensor = self._load_npy_as_tensor(sample.filepath)
        else:
            image_tensor = self._load_image_as_tensor(sample.filepath)

        output = {
            "image": image_tensor,
            "label": torch.tensor(float(sample.label), dtype=torch.float32),
            "filepath": str(sample.filepath.as_posix()),
            "metadata": sample.metadata,
        }
        return output

    def _load_npy_as_tensor(self, path: Path) -> torch.Tensor:
        """Load NPY array and convert to channel-first float tensor."""
        array = np.load(path, allow_pickle=False)

        if array.ndim == 2:
            array = np.expand_dims(array, axis=-1)
        if array.ndim != 3:
            raise ValueError(f"Unsupported NPY shape {array.shape} for file {path}")

        # Handle CHW arrays
        if array.shape[0] in (1, 3) and array.shape[2] not in (1, 3):
            array = np.transpose(array, (1, 2, 0))

        if array.shape[2] == 1:
            array = np.repeat(array, 3, axis=2)
        elif array.shape[2] > 3:
            array = array[:, :, :3]

        tensor = torch.from_numpy(array.astype(np.float32)).permute(2, 0, 1)
        return tensor

    def _load_image_as_tensor(self, path: Path) -> torch.Tensor:
        """Load PIL image, convert RGB, and apply configured transform."""
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            if self.transform is not None:
                tensor = self.transform(rgb)
            else:
                tensor = torch.from_numpy(np.asarray(rgb).astype(np.float32) / 255.0).permute(2, 0, 1)
        return tensor

    def labels(self) -> List[int]:
        """Return list of integer labels for sampler and statistics."""
        return [int(item.label) for item in self.samples]


def collate_batch(batch: Sequence[Dict]) -> Dict:
    """Custom collate function preserving filepaths and metadata lists."""
    images = torch.stack([item["image"] for item in batch], dim=0)
    labels = torch.stack([item["label"] for item in batch], dim=0)
    filepaths = [item["filepath"] for item in batch]
    metadata = [item["metadata"] for item in batch]
    return {
        "image": images,
        "label": labels,
        "filepath": filepaths,
        "metadata": metadata,
    }


def compute_dataset_statistics(dataset: FaceBinaryDataset) -> Dict:
    """Compute class distribution and rough channel mean/std statistics."""
    class_counts = compute_class_distribution(dataset.labels())

    if len(dataset) == 0:
        return {
            "size": 0,
            "class_counts": class_counts,
            "channel_mean": [0.0, 0.0, 0.0],
            "channel_std": [0.0, 0.0, 0.0],
        }

    running_sum = torch.zeros(3, dtype=torch.float64)
    running_sq_sum = torch.zeros(3, dtype=torch.float64)
    total_pixels = 0

    sample_count = min(len(dataset), 256)
    for idx in range(sample_count):
        tensor = dataset[idx]["image"].float()
        if tensor.ndim != 3:
            continue
        channels, height, width = tensor.shape
        if channels == 1:
            tensor = tensor.repeat(3, 1, 1)
        elif channels > 3:
            tensor = tensor[:3, :, :]

        running_sum += tensor.view(3, -1).sum(dim=1).double()
        running_sq_sum += (tensor.view(3, -1) ** 2).sum(dim=1).double()
        total_pixels += height * width

    if total_pixels == 0:
        channel_mean = [0.0, 0.0, 0.0]
        channel_std = [0.0, 0.0, 0.0]
    else:
        mean = running_sum / total_pixels
        var = (running_sq_sum / total_pixels) - (mean**2)
        std = torch.sqrt(torch.clamp(var, min=1e-12))
        channel_mean = [float(v) for v in mean]
        channel_std = [float(v) for v in std]

    return {
        "size": len(dataset),
        "class_counts": class_counts,
        "channel_mean": channel_mean,
        "channel_std": channel_std,
    }


def build_datasets(config: Dict, transforms_map: Dict, logger: logging.Logger) -> Dict[str, FaceBinaryDataset]:
    """Create train/val/test datasets and validate split leakage constraints."""
    metadata_csv = Path(config.get("metadata_csv", "")) if config.get("metadata_csv", "") else None

    datasets = {
        "train": FaceBinaryDataset(
            split="train",
            split_dir=Path(config["train_dir"]),
            transform=transforms_map["train"],
            metadata_csv=metadata_csv,
            allowed_image_extensions=config.get("allowed_extensions", {}).get("image", [".jpg", ".jpeg", ".png"]),
            allowed_array_extensions=config.get("allowed_extensions", {}).get("array", [".npy"]),
            logger=logger,
        ),
        "val": FaceBinaryDataset(
            split="val",
            split_dir=Path(config["val_dir"]),
            transform=transforms_map["val"],
            metadata_csv=metadata_csv,
            allowed_image_extensions=config.get("allowed_extensions", {}).get("image", [".jpg", ".jpeg", ".png"]),
            allowed_array_extensions=config.get("allowed_extensions", {}).get("array", [".npy"]),
            logger=logger,
        ),
        "test": FaceBinaryDataset(
            split="test",
            split_dir=Path(config["test_dir"]),
            transform=transforms_map["test"],
            metadata_csv=metadata_csv,
            allowed_image_extensions=config.get("allowed_extensions", {}).get("image", [".jpg", ".jpeg", ".png"]),
            allowed_array_extensions=config.get("allowed_extensions", {}).get("array", [".npy"]),
            logger=logger,
        ),
    }

    leakage, details = check_split_leakage(
        train_paths=[sample.filepath.as_posix() for sample in datasets["train"].samples],
        val_paths=[sample.filepath.as_posix() for sample in datasets["val"].samples],
        test_paths=[sample.filepath.as_posix() for sample in datasets["test"].samples],
    )

    if leakage:
        raise RuntimeError(f"Data leakage detected across splits: {details}")

    for split, dataset in datasets.items():
        stats = compute_dataset_statistics(dataset)
        logger.info(
            "Split '%s' stats | size=%d class_counts=%s",
            split,
            stats["size"],
            stats["class_counts"],
        )

    return datasets
