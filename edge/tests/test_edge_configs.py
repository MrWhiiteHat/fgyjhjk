from __future__ import annotations

from pathlib import Path

import yaml


EDGE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = EDGE_DIR / "on_device" / "configs"


def _load_config(name: str) -> dict:
    path = CONFIG_DIR / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_common_config_shape(config: dict) -> None:
    required_keys = [
        "app_name",
        "app_version",
        "model_name",
        "model_version",
        "inference_mode",
        "default_threshold",
        "input_size",
        "normalization_mean",
        "normalization_std",
        "storage_quota_mb",
        "privacy_mode",
    ]
    for key in required_keys:
        assert key in config

    assert 0.0 <= float(config["default_threshold"]) <= 1.0

    input_size = config["input_size"]
    assert isinstance(input_size, list)
    assert len(input_size) == 2
    assert input_size[0] > 0 and input_size[1] > 0

    mean = config["normalization_mean"]
    std = config["normalization_std"]
    assert len(mean) == 3
    assert len(std) == 3

    assert config["privacy_mode"] in {
        "strict_local",
        "user_selectable",
        "extension_minimum_retention",
    }


def test_edge_configs_have_required_fields_and_ranges() -> None:
    edge_cfg = _load_config("edge_config.yaml")
    mobile_cfg = _load_config("mobile_config.yaml")
    extension_cfg = _load_config("extension_config.yaml")

    for cfg in [edge_cfg, mobile_cfg, extension_cfg]:
        _assert_common_config_shape(cfg)

    assert edge_cfg["inference_mode"] in {"local", "backend", "auto", "backend_preferred"}
    assert mobile_cfg["inference_mode"] in {"local", "backend", "auto", "backend_preferred"}
    assert extension_cfg["inference_mode"] in {"local", "backend", "auto", "backend_preferred"}

    assert int(extension_cfg["extension_scan_limit"]) > 0
    assert int(mobile_cfg["mobile_camera_fps_cap"]) >= 0
