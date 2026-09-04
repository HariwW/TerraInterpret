from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image

from i2rsi.model_runtime import ModelRuntimeManager
from i2rsi.registry import MODEL_BY_ID
from i2rsi.settings import Settings


def _prediction_fixture(
    tmp_path: Path,
    sample: bytes,
) -> tuple[Image.Image, Path, np.ndarray]:
    primary = Image.open(io.BytesIO(sample)).convert("RGB")
    confidence = np.full((primary.height, primary.width), 0.8, dtype=np.float32)
    confidence[:, : primary.width // 2] = 0.4
    prediction = tmp_path / "prediction.npz"
    np.savez_compressed(
        prediction,
        labels=np.full(confidence.shape, 2, dtype=np.uint8),
        confidence=confidence,
        uncertainty=1.0 - confidence,
    )
    return primary, prediction, confidence


def test_loveda_marks_pixels_below_confidence_threshold_as_uncertain(
    settings: Settings,
    sample_images: dict[str, bytes],
    tmp_path: Path,
) -> None:
    primary, prediction, _ = _prediction_fixture(tmp_path, sample_images["land"])
    output_dir = tmp_path / "land-output"
    output_dir.mkdir()
    output = ModelRuntimeManager(settings)._render_external(
        card=MODEL_BY_ID["deeplabv3plus-r18-loveda"],
        primary=primary,
        output_dir=output_dir,
        prediction_path=prediction,
        metadata={"runtime_ms": 12.0},
        threshold=0.45,
    )

    assert output.metrics["rejected_pixel_pct"] == 50.0
    assert output.legend[-1] == {"label": "不确定", "colour": "#5b6679", "share": 0.5}


def test_loveda_road_filters_low_confidence_road_pixels(
    settings: Settings,
    sample_images: dict[str, bytes],
    tmp_path: Path,
) -> None:
    primary, prediction, _ = _prediction_fixture(tmp_path, sample_images["road"])
    output_dir = tmp_path / "road-output"
    output_dir.mkdir()
    output = ModelRuntimeManager(settings)._render_external(
        card=MODEL_BY_ID["deeplabv3plus-r18-loveda-road"],
        primary=primary,
        output_dir=output_dir,
        prediction_path=prediction,
        metadata={"runtime_ms": 12.0},
        threshold=0.45,
    )

    mask = np.asarray(Image.open(output_dir / "mask.png"))
    assert output.metrics["predicted_road_pct"] == 50.0
    assert not mask[:, : primary.width // 2].any()
    assert (mask[:, primary.width // 2 :] == 255).all()
