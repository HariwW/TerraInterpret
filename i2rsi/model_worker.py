"""Isolated PyTorch worker for optional pretrained models.

This file intentionally uses only stdlib imports at module import time. The main API
invokes it with ``.venv-models/bin/python`` so OpenMMLab/Ultralytics dependencies do
not alter the lightweight web environment.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import types
import urllib.request
from pathlib import Path
from typing import Any

MMSEG_MODELS = {
    "mmseg-loveda": {
        "backbone": "r18",
        "checkpoint": "deeplabv3plus-r18-loveda-ce0fa0ca.pth",
        "url": (
            "https://download.openmmlab.com/mmsegmentation/v0.5/deeplabv3plus/"
            "deeplabv3plus_r18-d8_512x512_80k_loveda/"
            "deeplabv3plus_r18-d8_512x512_80k_loveda_20211104_132800-ce0fa0ca.pth"
        ),
    },
    "mmseg-loveda-r50": {
        "backbone": "r50",
        "checkpoint": "deeplabv3plus-r50-loveda-f0720392.pth",
        "url": (
            "https://download.openmmlab.com/mmsegmentation/v0.5/deeplabv3plus/"
            "deeplabv3plus_r50-d8_512x512_80k_loveda/"
            "deeplabv3plus_r50-d8_512x512_80k_loveda_20211105_080442-f0720392.pth"
        ),
    },
    "mmseg-loveda-r101": {
        "backbone": "r101",
        "checkpoint": "deeplabv3plus-r101-loveda-4c1f297e.pth",
        "url": (
            "https://download.openmmlab.com/mmsegmentation/v0.5/deeplabv3plus/"
            "deeplabv3plus_r101-d8_512x512_80k_loveda/"
            "deeplabv3plus_r101-d8_512x512_80k_loveda_20211105_110759-4c1f297e.pth"
        ),
    },
}
MMSEG_BACKEND_ALIASES = {
    "mmseg-loveda-road": "mmseg-loveda",
    "mmseg-loveda-r50-road": "mmseg-loveda-r50",
}
YOLO_MODELS = {
    "ultralytics-obb": "yolo11n-obb.pt",
    "ultralytics-yolo26n-obb": "yolo26n-obb.pt",
    "ultralytics-yolo26s-obb": "yolo26s-obb.pt",
}
LOVEDA_CLASSES = (
    "background",
    "building",
    "road",
    "water",
    "barren",
    "forest",
    "agricultural",
)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _install_mmcv_lite_guard() -> None:
    """Let convolution-only MMSeg models import with mmcv-lite.

    MMSegmentation imports every optional head eagerly, including heads backed by
    ``mmcv._ext``. DeepLabV3+ R18 does not call those operators. The guard allows
    registration to finish while still raising an explicit error if an unavailable
    compiled operator is ever invoked.
    """
    try:
        import mmcv._ext  # type: ignore[import-not-found]  # noqa: F401

        return
    except ImportError:
        pass
    extension = types.ModuleType("mmcv._ext")
    extension.__file__ = "<mmcv-lite-guard>"

    def missing_operator(name: str):
        def unavailable(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError(
                f"MMCV operator {name} is unavailable in the portable mmcv-lite runtime"
            )

        return unavailable

    extension.__getattr__ = missing_operator  # type: ignore[attr-defined]
    sys.modules["mmcv._ext"] = extension


def _status(backend: str, cache_dir: Path) -> dict[str, Any]:
    if backend == "opencd" and platform.system() == "Darwin":
        return {
            "ready": False,
            "device": "unsupported",
            "weights_cached": False,
            "reason": "Open-CD Changer 依赖 MMCV 编译算子，当前 Apple Silicon 运行时不受支持。",
            "setup_hint": "请在 Linux + CUDA 环境运行，或配置远程模型 worker。",
        }
    try:
        import torch

        if backend.startswith("mmseg"):
            _install_mmcv_lite_guard()
            import mmcv  # noqa: F401
            import mmengine  # noqa: F401
            import mmseg  # noqa: F401
            import mmseg.apis  # noqa: F401
        elif backend.startswith("ultralytics"):
            import ultralytics  # noqa: F401
        elif backend == "opencd":
            import opencd  # noqa: F401
        else:
            raise RuntimeError(f"Unknown backend: {backend}")
        reported_device = (
            "cuda:0"
            if torch.cuda.is_available()
            else "cpu"
            if backend.startswith("mmseg")
            else _device()
        )
        return {
            "ready": True,
            "device": reported_device,
            "weights_cached": _weights_path(backend, cache_dir).exists(),
            "torch_version": torch.__version__,
        }
    except Exception as exc:
        return {
            "ready": False,
            "device": "unavailable",
            "weights_cached": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "setup_hint": "运行 make models-setup 安装隔离模型环境。",
        }


def _weights_path(backend: str, cache_dir: Path) -> Path:
    if backend.startswith("mmseg"):
        canonical = MMSEG_BACKEND_ALIASES.get(backend, backend)
        return cache_dir / str(MMSEG_MODELS[canonical]["checkpoint"])
    if backend.startswith("ultralytics"):
        return cache_dir / YOLO_MODELS[backend]
    return cache_dir / "changer-r18-levircd.pth"


def _download(url: str, target: Path) -> Path:
    if target.exists() and target.stat().st_size > 1024:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "TerraInterpret/2.3"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    partial.replace(target)
    return target


def _mmseg_config(backend: str) -> Path:
    import mmseg

    canonical = MMSEG_BACKEND_ALIASES.get(backend, backend)
    backbone = MMSEG_MODELS[canonical]["backbone"]
    filename = f"deeplabv3plus_{backbone}-d8_4xb4-80k_loveda-512x512.py"
    package_root = Path(mmseg.__file__).resolve().parent
    candidates = (
        package_root
        / ".mim"
        / "configs"
        / "deeplabv3plus"
        / filename,
        package_root.parent
        / "configs"
        / "deeplabv3plus"
        / filename,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("MMSegmentation LoveDA config is not installed")


def _run_mmseg(
    backend: str, primary: Path, cache_dir: Path, output: Path
) -> dict[str, Any]:
    import numpy as np
    import torch

    _install_mmcv_lite_guard()
    from mmseg.apis import inference_model, init_model

    canonical = MMSEG_BACKEND_ALIASES.get(backend, backend)
    spec = MMSEG_MODELS[canonical]
    checkpoint = _download(str(spec["url"]), _weights_path(backend, cache_dir))
    # MMCV's portable macOS build is CPU-safe; MPS remains opt-in for this backend.
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = init_model(str(_mmseg_config(backend)), str(checkpoint), device=device)
    prediction = inference_model(model, str(primary))
    labels = prediction.pred_sem_seg.data.squeeze().detach().cpu().numpy().astype(np.uint8)
    if hasattr(prediction, "seg_logits"):
        logits = prediction.seg_logits.data.detach().float().cpu()
        confidence = torch.softmax(logits, dim=0).amax(dim=0).numpy().astype(np.float32)
    else:
        confidence = np.ones(labels.shape, dtype=np.float32)
    np.savez_compressed(
        output,
        labels=labels,
        confidence=confidence,
        uncertainty=(1.0 - confidence).astype(np.float32),
    )
    return {
        "device": device,
        "framework": "MMSegmentation",
        "framework_version": __import__("mmseg").__version__,
        "weights": checkpoint.name,
        "classes": list(LOVEDA_CLASSES),
    }


def _run_yolo(
    backend: str, primary: Path, cache_dir: Path, output: Path, threshold: float
) -> dict[str, Any]:
    import numpy as np
    from PIL import Image, ImageDraw
    from ultralytics import YOLO
    from ultralytics import __version__ as ultralytics_version

    cache_dir.mkdir(parents=True, exist_ok=True)
    weights = _weights_path(backend, cache_dir)
    weight_name = YOLO_MODELS[backend]
    if not weights.exists():
        previous = Path.cwd()
        try:
            os.chdir(cache_dir)
            model = YOLO(weight_name)
        finally:
            os.chdir(previous)
    else:
        model = YOLO(str(weights))
    device = _device()
    result = model.predict(
        source=str(primary),
        conf=threshold,
        imgsz=1024,
        device=device,
        verbose=False,
    )[0]
    width, height = Image.open(primary).size
    mask_image = Image.new("L", (width, height), 0)
    confidence_image = Image.new("F", (width, height), 0.0)
    mask_draw = ImageDraw.Draw(mask_image)
    confidence_draw = ImageDraw.Draw(confidence_image)
    features: list[dict[str, Any]] = []
    names = result.names
    if result.obb is not None:
        polygons = result.obb.xyxyxyxy.detach().cpu().numpy()
        confidences = result.obb.conf.detach().cpu().numpy()
        classes = result.obb.cls.detach().cpu().numpy().astype(int)
        for index, (polygon, score, class_index) in enumerate(
            zip(polygons, confidences, classes, strict=True)
        ):
            points = [(float(x), float(y)) for x, y in polygon]
            mask_draw.polygon(points, fill=1)
            confidence_draw.polygon(points, fill=float(score))
            coordinates = [[round(x, 2), round(y, 2)] for x, y in points]
            coordinates.append(coordinates[0])
            features.append(
                {
                    "type": "Feature",
                    "id": index,
                    "properties": {
                        "label": str(names[class_index]),
                        "class_id": int(class_index),
                        "score": round(float(score), 5),
                        "score_proxy": round(float(score), 5),
                        "image_height": height,
                    },
                    "geometry": {"type": "Polygon", "coordinates": [coordinates]},
                }
            )
    mask = np.asarray(mask_image, dtype=np.uint8)
    confidence = np.asarray(confidence_image, dtype=np.float32)
    uncertainty = np.where(mask > 0, 1.0 - confidence, 0.0).astype(np.float32)
    np.savez_compressed(output, mask=mask, confidence=confidence, uncertainty=uncertainty)
    return {
        "device": device,
        "framework": "Ultralytics",
        "framework_version": ultralytics_version,
        "weights": weight_name,
        "features": {
            "type": "FeatureCollection",
            "name": f"terrainterpret-{weight_name.removesuffix('.pt')}-pixel-coordinates",
            "coordinate_reference": "pixel (origin: top-left)",
            "features": features,
        },
    }


def _run_opencd(
    primary: Path, secondary: Path | None, cache_dir: Path, output: Path
) -> dict[str, Any]:
    if secondary is None:
        raise ValueError("Open-CD inference requires two images")
    checkpoint = _weights_path("opencd", cache_dir)
    if not checkpoint.exists():
        raise FileNotFoundError(
            "Open-CD checkpoint is not cached; place the official Changer R18 weight at "
            f"{checkpoint}"
        )
    import numpy as np
    import opencd
    from opencd.apis import OpenCDInferencer

    package_root = Path(opencd.__file__).resolve().parent
    config = package_root / ".mim" / "configs" / "changer" / "changer_ex_r18_512x512_40k_levircd.py"
    inferencer = OpenCDInferencer(
        model=str(config),
        weights=str(checkpoint),
        device=_device(),
        classes=("unchanged", "changed"),
        palette=[[0, 0, 0], [255, 255, 255]],
    )
    result = inferencer([[str(primary), str(secondary)]], return_datasamples=True)
    sample = result["predictions"][0]
    labels = sample.pred_sem_seg.data.squeeze().detach().cpu().numpy().astype(np.uint8)
    confidence = np.ones(labels.shape, dtype=np.float32)
    if hasattr(sample, "seg_logits"):
        import torch

        logits = sample.seg_logits.data.detach().float().cpu()
        confidence = torch.softmax(logits, dim=0).amax(dim=0).numpy().astype(np.float32)
    np.savez_compressed(
        output,
        mask=(labels == 1).astype(np.uint8),
        confidence=confidence,
        uncertainty=(1.0 - confidence).astype(np.float32),
    )
    return {
        "device": _device(),
        "framework": "Open-CD",
        "framework_version": getattr(opencd, "__version__", "1.1"),
        "weights": checkpoint.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--backend", required=True)
    status_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--backend", required=True)
    run_parser.add_argument("--primary", type=Path, required=True)
    run_parser.add_argument("--secondary", type=Path)
    run_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()
    if args.command == "status":
        payload = _status(args.backend, args.cache_dir)
        _emit(payload)
        return 0 if payload["ready"] else 2
    started = time.perf_counter()
    try:
        if args.backend.startswith("mmseg"):
            metadata = _run_mmseg(args.backend, args.primary, args.cache_dir, args.output)
        elif args.backend.startswith("ultralytics"):
            metadata = _run_yolo(
                args.backend, args.primary, args.cache_dir, args.output, args.threshold
            )
        elif args.backend == "opencd":
            metadata = _run_opencd(args.primary, args.secondary, args.cache_dir, args.output)
        else:
            raise ValueError(f"Unknown backend: {args.backend}")
        _emit(
            {"ok": True, "runtime_ms": round((time.perf_counter() - started) * 1000, 2), **metadata}
        )
        return 0
    except Exception as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
