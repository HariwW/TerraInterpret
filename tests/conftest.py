from __future__ import annotations

import importlib
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from i2rsi.settings import Settings


def _render_image(kind: str, image_format: str = "PNG") -> bytes:
    image = Image.new("RGB", (96, 72), (38, 51, 67))
    draw = ImageDraw.Draw(image)

    if kind == "before":
        draw.rectangle((8, 8, 42, 33), fill=(72, 115, 78))
        draw.rectangle((54, 14, 82, 44), fill=(132, 126, 117))
    elif kind == "after":
        draw.rectangle((8, 8, 42, 33), fill=(72, 115, 78))
        draw.rectangle((50, 10, 90, 54), fill=(220, 215, 204))
        draw.line((0, 64, 95, 48), fill=(235, 235, 225), width=5)
    elif kind == "land":
        draw.rectangle((0, 0, 47, 35), fill=(35, 92, 196))
        draw.rectangle((48, 0, 95, 35), fill=(43, 169, 77))
        draw.rectangle((0, 36, 47, 71), fill=(196, 190, 181))
        draw.rectangle((48, 36, 95, 71), fill=(171, 126, 76))
    elif kind == "objects":
        draw.rectangle((10, 8, 28, 23), fill=(235, 235, 225))
        draw.ellipse((48, 14, 70, 34), fill=(211, 76, 71))
        draw.rectangle((22, 45, 66, 60), fill=(48, 158, 199))
    elif kind == "road":
        image.paste((55, 112, 64), (0, 0, 96, 72))
        draw.line((-5, 67, 101, 7), fill=(205, 201, 190), width=8)
        draw.line((15, -5, 55, 77), fill=(188, 187, 180), width=6)
    elif kind == "alternate":
        draw.rectangle((0, 0, 95, 71), fill=(173, 72, 113))
        draw.polygon(((5, 65), (48, 4), (91, 65)), fill=(239, 196, 73))
    else:  # pragma: no cover - protects this test helper from accidental misuse
        raise ValueError(f"Unknown synthetic image kind: {kind}")

    payload = io.BytesIO()
    image.save(payload, format=image_format, quality=90)
    return payload.getvalue()


@pytest.fixture
def sample_images() -> dict[str, bytes]:
    return {
        "before": _render_image("before"),
        "after": _render_image("after"),
        "land": _render_image("land", "JPEG"),
        "objects": _render_image("objects", "JPEG"),
        "road": _render_image("road"),
        "alternate": _render_image("alternate"),
    }


@pytest.fixture
def settings(tmp_path: Path, sample_images: dict[str, bytes]) -> Settings:
    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "index.html").write_text("<!doctype html><title>I2RSI test</title>")

    demo_archive = tmp_path / "data_demo.zip"
    with zipfile.ZipFile(demo_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("CD/test_1_A.png", sample_images["before"])
        archive.writestr("CD/test_1_B.png", sample_images["after"])
        archive.writestr("OC/T018147.jpg", sample_images["land"])
        archive.writestr("OD/aircraft_14.jpg", sample_images["objects"])
        archive.writestr("OE/img-1.png", sample_images["road"])

    return Settings(
        project_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        static_root=static_root,
        demo_archive=demo_archive,
        max_upload_bytes=64 * 1024,
        max_image_edge=128,
        job_retention=20,
    )


@pytest.fixture
def app(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    # i2rsi.app exposes a module-level ASGI app. Patch its default settings before the
    # first import so test collection never writes artifacts into the repository.
    monkeypatch.setattr(
        Settings,
        "from_environment",
        classmethod(lambda cls: settings),
    )
    app_module = importlib.import_module("i2rsi.app")
    return app_module.create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
