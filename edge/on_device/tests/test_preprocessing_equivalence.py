from __future__ import annotations

import numpy as np
import pytest

from edge.on_device.preprocessing import image_preprocess as image_preprocess_module
from edge.on_device.preprocessing.normalization import denormalize_image, normalize_image, to_nchw_batch, to_nhwc_batch


def test_normalize_denormalize_roundtrip() -> None:
    image = np.random.rand(6, 6, 3).astype(np.float32)
    normalized = normalize_image(image)
    restored = denormalize_image(normalized)
    assert np.allclose(image, restored, atol=1e-5)


def test_tensor_layout_helpers() -> None:
    image = np.random.rand(8, 8, 3).astype(np.float32)
    nchw = to_nchw_batch(image)
    nhwc = to_nhwc_batch(image)

    assert nchw.shape == (1, 3, 8, 8)
    assert nhwc.shape == (1, 8, 8, 3)
    assert np.allclose(np.transpose(nchw[0], (1, 2, 0)), nhwc[0], atol=1e-6)


def test_preprocess_layout_equivalence(monkeypatch: pytest.MonkeyPatch) -> None:
    base_image = np.full((8, 8, 3), fill_value=127, dtype=np.uint8)

    monkeypatch.setattr(image_preprocess_module, "load_image_rgb", lambda _path: base_image)
    monkeypatch.setattr(image_preprocess_module, "resize_image", lambda image, _size: image)

    nchw = image_preprocess_module.preprocess_image_for_model("unused.jpg", tensor_layout="nchw")
    nhwc = image_preprocess_module.preprocess_image_for_model("unused.jpg", tensor_layout="nhwc")

    assert nchw.shape == (1, 3, 8, 8)
    assert nhwc.shape == (1, 8, 8, 3)
    assert np.allclose(np.transpose(nchw[0], (1, 2, 0)), nhwc[0], atol=1e-6)

    with pytest.raises(ValueError):
        image_preprocess_module.preprocess_image_for_model("unused.jpg", tensor_layout="bad_layout")
