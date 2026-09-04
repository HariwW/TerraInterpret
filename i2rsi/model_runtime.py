from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .engine import DemoInterpretationEngine, EngineOutput, sha256_file
from .models import ModelCard, ModelRuntimeStatus, TaskType
from .registry import DEFAULT_MODEL_PRIORITY, MODEL_BY_ID, MODEL_WEIGHT_FILENAMES
from .settings import Settings

LOVEDA_CLASSES = ("背景", "建筑", "道路", "水体", "裸地", "森林", "农业用地")
LOVEDA_COLOURS = (
    (255, 255, 255),
    (255, 0, 0),
    (255, 255, 0),
    (0, 0, 255),
    (159, 129, 183),
    (0, 255, 0),
    (255, 195, 128),
)
LOVEDA_HEX = ("#ffffff", "#ff0000", "#ffff00", "#0000ff", "#9f81b7", "#00ff00", "#ffc380")


class ModelUnavailableError(ValueError):
    pass


class ModelRuntimeManager:
    """Routes registered models without importing optional ML libraries in the API."""

    id = "hybrid-model-router"
    version = "1.0.0"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.python = settings.model_runtime_python or (
            settings.project_root / ".venv-models" / "bin" / "python"
        )
        self.cache_root = settings.model_cache_root or (settings.artifact_root / "model-cache")
        self.worker = settings.project_root / "i2rsi" / "model_worker.py"
        self.lite = DemoInterpretationEngine(max_image_edge=settings.max_image_edge)
        self._status_cache: dict[str, ModelRuntimeStatus] = {}
        self._lock = threading.RLock()

    def status(self, card: ModelCard, *, refresh: bool = False) -> ModelRuntimeStatus:
        if card.backend in {"lite", "builtin-robust-change"}:
            return ModelRuntimeStatus(
                model_id=card.id,
                ready=True,
                backend=card.backend,
                runtime=card.runtime,
                device="cpu",
                weights_cached=True,
            )
        with self._lock:
            cache_key = self._runtime_family(card.backend)
            if not refresh and cache_key in self._status_cache:
                cached = self._status_cache[cache_key]
                return cached.model_copy(
                    update={
                        "model_id": card.id,
                        "backend": card.backend,
                        "weights_cached": self._weights_cached(card.id, cached.weights_cached),
                    }
                )
        if not self.python.exists():
            status = ModelRuntimeStatus(
                model_id=card.id,
                ready=False,
                backend=card.backend,
                runtime=card.runtime,
                device="unavailable",
                reason=f"隔离模型环境不存在：{self.python}",
                setup_hint="在项目目录运行 make models-setup。",
            )
        else:
            command = [
                str(self.python),
                str(self.worker),
                "status",
                "--backend",
                card.backend,
                "--cache-dir",
                str(self.cache_root),
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=45,
                    check=False,
                )
                payload = self._json_line(completed.stdout)
                status = ModelRuntimeStatus(
                    model_id=card.id,
                    ready=bool(payload.get("ready")),
                    backend=card.backend,
                    runtime=card.runtime,
                    device=str(payload.get("device", "unavailable")),
                    weights_cached=self._weights_cached(
                        card.id, bool(payload.get("weights_cached"))
                    ),
                    reason=payload.get("reason"),
                    setup_hint=payload.get("setup_hint"),
                )
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                status = ModelRuntimeStatus(
                    model_id=card.id,
                    ready=False,
                    backend=card.backend,
                    runtime=card.runtime,
                    device="unavailable",
                    reason=f"模型运行时检查失败：{exc}",
                    setup_hint="运行 make models-setup，并检查隔离环境输出。",
                )
        with self._lock:
            self._status_cache[self._runtime_family(card.backend)] = status
        return status

    def statuses(self, *, refresh: bool = False) -> dict[str, ModelRuntimeStatus]:
        refreshed_families: set[str] = set()
        statuses: dict[str, ModelRuntimeStatus] = {}
        for model_id, card in MODEL_BY_ID.items():
            family = self._runtime_family(card.backend)
            should_refresh = refresh and family not in refreshed_families
            statuses[model_id] = self.status(card, refresh=should_refresh)
            refreshed_families.add(family)
        return statuses

    def preferred_model_id(
        self,
        task: TaskType,
        statuses: dict[str, ModelRuntimeStatus] | None = None,
    ) -> str:
        """Resolve the strongest balanced model that can run in this environment."""
        resolved = statuses or {}
        for model_id in DEFAULT_MODEL_PRIORITY[task]:
            card = MODEL_BY_ID[model_id]
            status = resolved.get(model_id) or self.status(card)
            # Open-CD does not auto-download its checkpoint, so import readiness alone
            # is not enough to make it a safe default.
            if status.ready and (card.backend != "opencd" or status.weights_cached):
                return model_id
        for card in MODEL_BY_ID.values():
            if card.task is task and (resolved.get(card.id) or self.status(card)).ready:
                return card.id
        raise ModelUnavailableError(f"No ready model supports task {task.value}")

    def ensure_ready(self, model_id: str) -> None:
        card = MODEL_BY_ID[model_id]
        status = self.status(card)
        if not status.ready:
            detail = status.reason or "模型运行时尚未就绪"
            hint = f" {status.setup_hint}" if status.setup_hint else ""
            raise ModelUnavailableError(f"Model {model_id} unavailable: {detail}.{hint}")

    def run(
        self,
        *,
        task: TaskType,
        model_id: str,
        primary_path: Path,
        output_dir: Path,
        secondary_path: Path | None = None,
        threshold: float = 0.62,
    ) -> EngineOutput:
        card = MODEL_BY_ID.get(model_id)
        if card is None or card.task is not task:
            raise ValueError(f"Model {model_id} does not support task {task.value}")
        if card.backend in {"lite", "builtin-robust-change"}:
            return self.lite.run(
                task=task,
                model_id=model_id,
                primary_path=primary_path,
                secondary_path=secondary_path,
                output_dir=output_dir,
                threshold=threshold,
            )
        self.ensure_ready(model_id)
        return self._run_external(
            card=card,
            primary_path=primary_path,
            secondary_path=secondary_path,
            output_dir=output_dir,
            threshold=threshold,
        )

    def _run_external(
        self,
        *,
        card: ModelCard,
        primary_path: Path,
        secondary_path: Path | None,
        output_dir: Path,
        threshold: float,
    ) -> EngineOutput:
        output_dir.mkdir(parents=True, exist_ok=True)
        primary = self._normalised_image(primary_path)
        primary.save(output_dir / "original.png", optimize=True)
        worker_secondary: Path | None = None
        if secondary_path is not None:
            secondary = self._normalised_image(secondary_path, size=primary.size)
            worker_secondary = output_dir / "secondary.png"
            secondary.save(worker_secondary, optimize=True)
        prediction_path = output_dir / "prediction.npz"
        command = [
            str(self.python),
            str(self.worker),
            "run",
            "--backend",
            card.backend,
            "--primary",
            str(output_dir / "original.png"),
            "--cache-dir",
            str(self.cache_root),
            "--output",
            str(prediction_path),
            "--threshold",
            str(threshold),
        ]
        if worker_secondary is not None:
            command.extend(["--secondary", str(worker_secondary)])
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20 * 60,
            check=False,
        )
        try:
            metadata = self._json_line(completed.stdout)
        except ValueError as exc:
            detail = completed.stderr.strip()[-1200:] or "worker returned no JSON"
            raise RuntimeError(f"Model worker failed: {detail}") from exc
        if completed.returncode != 0 or not metadata.get("ok"):
            raise RuntimeError(str(metadata.get("error") or completed.stderr)[-1200:])
        return self._render_external(
            card=card,
            primary=primary,
            output_dir=output_dir,
            prediction_path=prediction_path,
            metadata=metadata,
            threshold=threshold,
        )

    def _render_external(
        self,
        *,
        card: ModelCard,
        primary: Image.Image,
        output_dir: Path,
        prediction_path: Path,
        metadata: dict[str, Any],
        threshold: float,
    ) -> EngineOutput:
        with np.load(prediction_path) as arrays:
            confidence = np.asarray(arrays["confidence"], dtype=np.float32)
            uncertainty = np.asarray(arrays["uncertainty"], dtype=np.float32)
            labels = np.asarray(arrays["labels"], dtype=np.uint8) if "labels" in arrays else None
            mask = np.asarray(arrays["mask"], dtype=np.uint8) > 0 if "mask" in arrays else None
        width, height = primary.size
        features = metadata.get("features")
        metrics: dict[str, float | int | str]
        if card.backend.startswith("mmseg"):
            if labels is None:
                raise RuntimeError("MMSeg worker returned no label raster")
            if card.backend.endswith("road"):
                mask = (labels == 2) & (confidence >= threshold)
                colour = np.zeros((height, width, 3), dtype=np.float32)
                colour[mask] = np.asarray((255, 190, 79), dtype=np.float32) / 255.0
                alpha = mask.astype(np.float32) * 0.66
                share = float(mask.mean())
                legend = [
                    {"label": "道路", "colour": "#ffbe4f", "share": round(share, 4)},
                    {"label": "非道路", "colour": "#25304a", "share": round(1 - share, 4)},
                ]
                metrics = {
                    "predicted_road_pct": round(share * 100, 2),
                    "mean_model_confidence": round(float(confidence.mean()), 3),
                    "rejected_pixel_pct": round(float((confidence < threshold).mean()) * 100, 2),
                }
                summary = (
                    "道路掩膜由 LoveDA 七类预训练模型的 road 类抽取得到；"
                    "拓扑连通性仍需后处理和人工核验。"
                )
                features = self.lite._features_from_mask(mask, "road")
                mask_artifact = mask.astype(np.uint8) * 255
            else:
                accepted = confidence >= threshold
                shares = [float(((labels == index) & accepted).mean()) for index in range(7)]
                colour = np.asarray(LOVEDA_COLOURS, dtype=np.float32)[labels] / 255.0
                colour[~accepted] = np.asarray((91, 102, 121), dtype=np.float32) / 255.0
                alpha = np.where(accepted, 0.58, 0.28).astype(np.float32)
                legend = [
                    {"label": label, "colour": LOVEDA_HEX[index], "share": round(shares[index], 4)}
                    for index, label in enumerate(LOVEDA_CLASSES)
                ]
                rejected_share = float((~accepted).mean())
                legend.append(
                    {"label": "不确定", "colour": "#5b6679", "share": round(rejected_share, 4)}
                )
                metrics = {
                    "class_count": 7,
                    "building_pct": round(shares[1] * 100, 2),
                    "road_pct": round(shares[2] * 100, 2),
                    "mean_model_confidence": round(float(confidence.mean()), 3),
                    "rejected_pixel_pct": round(rejected_share * 100, 2),
                }
                summary = (
                    f"结果来自 {card.name} 公开预训练权重；"
                    "跨地区、跨传感器结论需用本地真值评测。"
                )
                features = self.lite._features_from_mask(
                    (labels == 1) & accepted, "building"
                )
                mask_artifact = np.round(labels * (255 / 6)).astype(np.uint8)
        else:
            if mask is None:
                raise RuntimeError("Model worker returned no mask raster")
            mask_artifact = mask.astype(np.uint8) * 255
            share = float(mask.mean())
            if card.backend.startswith("ultralytics"):
                colour_image = primary.copy()
                draw = ImageDraw.Draw(colour_image)
                feature_items = (features or {}).get("features", [])
                for feature in feature_items:
                    points = [tuple(point) for point in feature["geometry"]["coordinates"][0][:-1]]
                    properties = feature["properties"]
                    draw.line(points + [points[0]], fill=(239, 84, 117), width=max(2, width // 360))
                    draw.text(
                        points[0],
                        f"{properties['label']} {properties['score']:.2f}",
                        fill=(255, 255, 255),
                    )
                colour = np.asarray(colour_image, dtype=np.float32) / 255.0
                alpha = np.ones((height, width), dtype=np.float32)
                metrics = {
                    "detection_count": len(feature_items),
                    "mean_model_confidence": round(
                        float(np.mean([item["properties"]["score"] for item in feature_items]))
                        if feature_items
                        else 0.0,
                        3,
                    ),
                }
                legend = [{"label": "DOTA 旋转框", "colour": "#ef5475", "share": 1.0}]
                summary = (
                    f"旋转框来自 {card.name} 的 DOTA 预训练权重；"
                    "类别外目标和域外影像需要独立评测。"
                )
            else:
                mask &= confidence >= threshold
                colour = np.zeros((height, width, 3), dtype=np.float32)
                colour[mask] = np.asarray((239, 84, 117), dtype=np.float32) / 255.0
                alpha = mask.astype(np.float32) * 0.68
                metrics = {
                    "predicted_change_pct": round(share * 100, 2),
                    "mean_model_confidence": round(
                        float(confidence[mask].mean()) if mask.any() else 0.0, 3
                    ),
                }
                legend = [
                    {"label": "预测变化", "colour": "#ef5475", "share": round(share, 4)},
                    {"label": "稳定区域", "colour": "#25304a", "share": round(1 - share, 4)},
                ]
                summary = (
                    "变化掩膜来自 Open-CD Changer R18 LEVIR-CD 预训练权重；"
                    "影像配准和域外精度需独立核验。"
                )
                features = self.lite._features_from_mask(mask, "change")
        overlay = self.lite._blend(primary, colour, alpha)
        overlay.save(output_dir / "overlay.png", optimize=True)
        Image.fromarray(mask_artifact, mode="L").save(output_dir / "mask.png", optimize=True)
        self.lite._uncertainty_image(uncertainty).save(
            output_dir / "uncertainty.png", optimize=True
        )
        feature_collection = features or {"type": "FeatureCollection", "features": []}
        (output_dir / "features.geojson").write_text(
            json.dumps(feature_collection, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metrics.update(
            {
                "runtime_ms": float(metadata["runtime_ms"]),
                "width_px": width,
                "height_px": height,
            }
        )
        files = {
            "original": (output_dir / "original.png", "原始影像", "image/png"),
            "overlay": (output_dir / "overlay.png", "解译叠加", "image/png"),
            "mask": (output_dir / "mask.png", "预测掩膜", "image/png"),
            "uncertainty": (output_dir / "uncertainty.png", "模型不确定性", "image/png"),
            "features": (output_dir / "features.geojson", "像素坐标矢量", "application/geo+json"),
        }
        secondary_file = output_dir / "secondary.png"
        if secondary_file.exists():
            files["secondary"] = (secondary_file, "后时相影像", "image/png")
        weights = self.cache_root / str(metadata.get("weights", ""))
        provenance = {
            "engine": self.id,
            "engine_version": self.version,
            "backend": card.backend,
            "runtime": card.runtime,
            "framework": metadata.get("framework"),
            "framework_version": metadata.get("framework_version"),
            "device": metadata.get("device"),
            "weights": metadata.get("weights"),
            "weights_sha256": sha256_file(weights) if weights.is_file() else None,
            "reproducibility": "public pretrained checkpoint; deterministic mode not guaranteed",
        }
        return EngineOutput(
            metrics=metrics,
            histogram=self.lite._histogram(confidence),
            legend=legend,
            summary=summary,
            files=files,
            features=feature_collection,
            provenance=provenance,
        )

    def _normalised_image(self, path: Path, size: tuple[int, int] | None = None) -> Image.Image:
        try:
            image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        except Exception as exc:
            raise ValueError("The uploaded file is not a readable RGB image") from exc
        if size is not None:
            return image.resize(size, Image.Resampling.BILINEAR) if image.size != size else image
        if max(image.size) > self.settings.max_image_edge:
            scale = self.settings.max_image_edge / max(image.size)
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        return image

    @staticmethod
    def _json_line(stdout: str) -> dict[str, Any]:
        for line in reversed(stdout.splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise ValueError("no JSON object in worker output")

    @staticmethod
    def _runtime_family(backend: str) -> str:
        if backend.startswith("mmseg"):
            return "mmseg"
        if backend.startswith("ultralytics"):
            return "ultralytics"
        return backend

    def _weights_cached(self, model_id: str, worker_value: bool) -> bool:
        filename = MODEL_WEIGHT_FILENAMES.get(model_id)
        return (self.cache_root / filename).is_file() if filename else worker_value
