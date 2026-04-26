"""Transform builders for train/validation/test pipelines."""

from __future__ import annotations

import io
import random
from typing import Dict

from PIL import Image
from torchvision import transforms


class RandomJPEGCompression:
    """Apply random JPEG compression artifacts for robustness augmentation."""

    def __init__(self, quality_min: int = 60, quality_max: int = 95, p: float = 0.0) -> None:
        self.quality_min = int(quality_min)
        self.quality_max = int(quality_max)
        self.p = float(p)

    def __call__(self, image: Image.Image) -> Image.Image:
        """Compress and decode image with randomized JPEG quality."""
        if random.random() > self.p:
            return image

        quality = random.randint(self.quality_min, self.quality_max)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        compressed = Image.open(buffer).convert("RGB")
        return compressed


def _defaults_by_policy(policy: str) -> Dict:
    """Resolve default augmentation knobs for a policy level."""
    key = str(policy).strip().lower()
    if key == "strong":
        return {
            "flip_p": 0.5,
            "rotation_deg": 15,
            "jitter": (0.2, 0.2, 0.2, 0.05),
            "blur_enabled": True,
            "jpeg_enabled": True,
            "jpeg_p": 0.4,
        }
    if key == "mild":
        return {
            "flip_p": 0.5,
            "rotation_deg": 7,
            "jitter": (0.1, 0.1, 0.05, 0.02),
            "blur_enabled": False,
            "jpeg_enabled": False,
            "jpeg_p": 0.0,
        }
    return {
        "flip_p": 0.0,
        "rotation_deg": 0,
        "jitter": (0.0, 0.0, 0.0, 0.0),
        "blur_enabled": False,
        "jpeg_enabled": False,
        "jpeg_p": 0.0,
    }


def build_train_transforms(config: Dict) -> transforms.Compose:
    """Build training transforms with config-driven augmentation controls."""
    image_size = int(config["image_size"])
    aug_cfg = dict(config.get("train_augmentations", {}))
    defaults = _defaults_by_policy(aug_cfg.get("policy", "mild"))

    mean = config.get("normalization", {}).get("mean", [0.485, 0.456, 0.406])
    std = config.get("normalization", {}).get("std", [0.229, 0.224, 0.225])

    transform_list = []

    if bool(aug_cfg.get("resize", True)):
        transform_list.append(transforms.Resize((image_size, image_size)))

    flip_cfg = aug_cfg.get("horizontal_flip", {}) or {}
    if bool(flip_cfg.get("enabled", defaults["flip_p"] > 0.0)):
        transform_list.append(transforms.RandomHorizontalFlip(p=float(flip_cfg.get("p", defaults["flip_p"]))))

    rotation_cfg = aug_cfg.get("rotation", {}) or {}
    if bool(rotation_cfg.get("enabled", defaults["rotation_deg"] > 0)):
        transform_list.append(transforms.RandomRotation(degrees=float(rotation_cfg.get("degrees", defaults["rotation_deg"]))))

    jitter_cfg = aug_cfg.get("color_jitter", {}) or {}
    if bool(jitter_cfg.get("enabled", any(v > 0 for v in defaults["jitter"]))):
        transform_list.append(
            transforms.ColorJitter(
                brightness=float(jitter_cfg.get("brightness", defaults["jitter"][0])),
                contrast=float(jitter_cfg.get("contrast", defaults["jitter"][1])),
                saturation=float(jitter_cfg.get("saturation", defaults["jitter"][2])),
                hue=float(jitter_cfg.get("hue", defaults["jitter"][3])),
            )
        )

    blur_cfg = aug_cfg.get("gaussian_blur", {}) or {}
    if bool(blur_cfg.get("enabled", defaults["blur_enabled"])):
        kernel_size = int(blur_cfg.get("kernel_size", 3))
        sigma = tuple(blur_cfg.get("sigma", [0.1, 1.2]))
        transform_list.append(transforms.GaussianBlur(kernel_size=kernel_size, sigma=sigma))

    jpeg_cfg = aug_cfg.get("jpeg_compression", {}) or {}
    if bool(jpeg_cfg.get("enabled", defaults["jpeg_enabled"])):
        transform_list.append(
            RandomJPEGCompression(
                quality_min=int(jpeg_cfg.get("quality_min", 60)),
                quality_max=int(jpeg_cfg.get("quality_max", 95)),
                p=float(jpeg_cfg.get("p", defaults["jpeg_p"])),
            )
        )

    transform_list.append(transforms.ToTensor())

    if bool(aug_cfg.get("normalize", True)):
        transform_list.append(transforms.Normalize(mean=mean, std=std))

    return transforms.Compose(transform_list)


def build_eval_transforms(config: Dict, split: str) -> transforms.Compose:
    """Build deterministic validation/test transforms."""
    image_size = int(config["image_size"])
    aug_cfg = dict(config.get(f"{split}_augmentations", {}))

    mean = config.get("normalization", {}).get("mean", [0.485, 0.456, 0.406])
    std = config.get("normalization", {}).get("std", [0.229, 0.224, 0.225])

    transform_list = []
    if bool(aug_cfg.get("resize", True)):
        transform_list.append(transforms.Resize((image_size, image_size)))

    transform_list.append(transforms.ToTensor())

    if bool(aug_cfg.get("normalize", True)):
        transform_list.append(transforms.Normalize(mean=mean, std=std))

    return transforms.Compose(transform_list)


def build_transforms(config: Dict) -> Dict[str, transforms.Compose]:
    """Build transform map for train/val/test splits."""
    return {
        "train": build_train_transforms(config),
        "val": build_eval_transforms(config, split="val"),
        "test": build_eval_transforms(config, split="test"),
    }
