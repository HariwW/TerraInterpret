from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .models import TaskType

PALETTE = {
    "change": (239, 84, 117),
    "road": (255, 190, 79),
    "water": (60, 149, 255),
    "vegetation": (59, 203, 137),
    "built_up": (244, 118, 98),
    "bare_land": (196, 166, 117),
}


@dataclass(slots=True)
class EngineOutput:
    metrics: dict[str, float | int | str]
    histogram: list[int]
    legend: list[dict[str, str | int | float]]
    summary: str
    files: dict[str, tuple[Path, str, str]]
    features: dict[str, Any]
    provenance: dict[str, Any]


class DemoInterpretationEngine:
    """Transparent CPU baselines for product and reproducibility demonstrations.

    These algorithms deliberately do not present themselves as trained remote-sensing
    models. They keep the complete V2 workflow runnable without unavailable 2022 Paddle
    weights and provide honest baselines that can later be replaced through an adapter.
    """

    id = "transparent-cpu-baselines"
    version = "2.0.0"

    def __init__(self, max_image_edge: int = 1536) -> None:
        self.max_image_edge = max_image_edge

    def run(
        self,
        *,
        task: TaskType,
        primary_path: Path,
        output_dir: Path,
        secondary_path: Path | None = None,
        threshold: float = 0.62,
        model_id: str | None = None,
    ) -> EngineOutput:
        started = time.perf_counter()
        output_dir.mkdir(parents=True, exist_ok=True)
        primary_image, primary = self._read_image(primary_path)

        if task is TaskType.CHANGE_DETECTION:
            if secondary_path is None:
                raise ValueError("Change detection requires a secondary image")
            secondary_image, secondary = self._read_image(secondary_path)
            if secondary_image.size != primary_image.size:
                secondary_image = secondary_image.resize(
                    primary_image.size, Image.Resampling.BILINEAR
                )
                secondary = np.asarray(secondary_image, dtype=np.float32) / 255.0
            result = (
                self._robust_change_detection(primary, secondary, threshold)
                if model_id == "geochange-robust-v3"
                else self._change_detection(primary, secondary, threshold)
            )
            display_base = secondary_image
            secondary_image.save(output_dir / "secondary.png", optimize=True)
        elif task is TaskType.LAND_COVER:
            result = self._land_cover(primary)
            display_base = primary_image
        elif task is TaskType.OBJECT_DETECTION:
            result = self._object_detection(primary)
            display_base = primary_image
        elif task is TaskType.ROAD_EXTRACTION:
            result = self._road_extraction(primary, threshold)
            display_base = primary_image
        else:  # pragma: no cover - exhaustive protection for future task values
            raise ValueError(f"Unsupported task: {task}")

        primary_image.save(output_dir / "original.png", optimize=True)
        overlay = self._blend(display_base, result["colour"], result["alpha"])
        overlay.save(output_dir / "overlay.png", optimize=True)
        Image.fromarray((result["mask"] * 255).astype(np.uint8), mode="L").save(
            output_dir / "mask.png", optimize=True
        )
        uncertainty = self._uncertainty_image(result["uncertainty"])
        uncertainty.save(output_dir / "uncertainty.png", optimize=True)

        features = result["features"]
        (output_dir / "features.geojson").write_text(
            json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        runtime_ms = round((time.perf_counter() - started) * 1000, 2)
        metrics = {
            **result["metrics"],
            "runtime_ms": runtime_ms,
            "width_px": primary_image.width,
            "height_px": primary_image.height,
        }
        files = {
            "original": (output_dir / "original.png", "原始影像", "image/png"),
            "overlay": (output_dir / "overlay.png", "解译叠加", "image/png"),
            "mask": (output_dir / "mask.png", "预测掩膜", "image/png"),
            "uncertainty": (
                output_dir / "uncertainty.png",
                "不确定性代理",
                "image/png",
            ),
            "features": (
                output_dir / "features.geojson",
                "像素坐标矢量",
                "application/geo+json",
            ),
        }
        if task is TaskType.CHANGE_DETECTION:
            files["secondary"] = (
                output_dir / "secondary.png",
                "后时相影像",
                "image/png",
            )
        robust_change = model_id == "geochange-robust-v3"
        return EngineOutput(
            metrics=metrics,
            histogram=self._histogram(result["confidence"]),
            legend=result["legend"],
            summary=result["summary"],
            files=files,
            features=features,
            provenance={
                "engine": "robust-change-cpu" if robust_change else self.id,
                "engine_version": "3.0.0" if robust_change else self.version,
                "backend": "builtin-robust-change" if robust_change else "lite",
                "device": "cpu",
                "model_id": model_id,
                "reproducibility": "deterministic CPU baseline",
            },
        )

    def _read_image(self, path: Path) -> tuple[Image.Image, np.ndarray]:
        try:
            image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        except Exception as exc:  # Pillow exposes several decoder-specific exceptions
            raise ValueError("The uploaded file is not a readable RGB image") from exc
        width, height = image.size
        if max(width, height) > self.max_image_edge:
            scale = self.max_image_edge / max(width, height)
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
        return image, np.asarray(image, dtype=np.float32) / 255.0

    @staticmethod
    def _normalise(values: np.ndarray) -> np.ndarray:
        low = float(np.quantile(values, 0.02))
        high = float(np.quantile(values, 0.98))
        if high - low < 1e-6:
            return np.zeros_like(values, dtype=np.float32)
        return np.clip((values - low) / (high - low), 0.0, 1.0).astype(np.float32)

    @staticmethod
    def _gradient(gray: np.ndarray) -> np.ndarray:
        grad_y, grad_x = np.gradient(gray)
        return np.sqrt(grad_x * grad_x + grad_y * grad_y)

    def _change_detection(
        self, before: np.ndarray, after: np.ndarray, threshold: float
    ) -> dict[str, Any]:
        delta = np.mean(np.abs(after - before), axis=2)
        local_structure = self._gradient(np.mean(after, axis=2))
        score = self._normalise(delta * 0.86 + local_structure * 0.14)
        adaptive = float(np.quantile(score, np.clip(0.76 + threshold * 0.18, 0.78, 0.93)))
        raw_mask = score >= adaptive
        mask_image = Image.fromarray((raw_mask * 255).astype(np.uint8), mode="L")
        mask_image = mask_image.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MaxFilter(3))
        mask = np.asarray(mask_image, dtype=np.uint8) > 0
        confidence = np.clip((score - adaptive) / max(1e-6, 1.0 - adaptive), 0.0, 1.0)
        uncertainty = np.clip(1.0 - np.abs(score - adaptive) / 0.28, 0.0, 1.0)
        colour = np.zeros_like(after)
        colour[mask] = np.asarray(PALETTE["change"], dtype=np.float32) / 255.0
        alpha = mask.astype(np.float32) * 0.68
        coverage = float(mask.mean())
        selected = confidence[mask]
        mean_confidence = float(selected.mean()) if selected.size else 0.0
        features = self._features_from_mask(mask, "change")
        return {
            "mask": mask,
            "colour": colour,
            "alpha": alpha,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "features": features,
            "metrics": {
                "predicted_change_pct": round(coverage * 100, 2),
                "mean_confidence_proxy": round(mean_confidence, 3),
                "mean_uncertainty_proxy": round(float(uncertainty.mean()), 3),
                "region_count": len(features["features"]),
            },
            "legend": [
                {"label": "预测变化", "colour": "#ef5475", "share": round(coverage, 4)},
                {"label": "稳定区域", "colour": "#25304a", "share": round(1 - coverage, 4)},
            ],
            "summary": "检测到的区域是可解释差异基线输出；季节、光照和配准误差仍需人工核验。",
        }

    def _robust_change_detection(
        self, before: np.ndarray, after: np.ndarray, threshold: float
    ) -> dict[str, Any]:
        """Deterministic change baseline robust to small shifts and radiometry drift."""
        shift_y, shift_x = self._estimate_translation(before, after)
        aligned = self._shift_image(before, shift_y, shift_x, fill=after)

        adjusted = np.empty_like(aligned)
        for channel in range(3):
            source = aligned[..., channel]
            target = after[..., channel]
            source_median = float(np.median(source))
            target_median = float(np.median(target))
            source_scale = float(np.quantile(source, 0.90) - np.quantile(source, 0.10))
            target_scale = float(np.quantile(target, 0.90) - np.quantile(target, 0.10))
            adjusted[..., channel] = np.clip(
                (source - source_median) * target_scale / max(source_scale, 0.05)
                + target_median,
                0.0,
                1.0,
            )

        before_gray = adjusted.mean(axis=2)
        after_gray = after.mean(axis=2)
        colour_delta = np.mean(np.abs(after - adjusted), axis=2)
        luminance_delta = np.abs(after_gray - before_gray)
        structure_delta = np.abs(self._gradient(after_gray) - self._gradient(before_gray))
        score = self._normalise(
            colour_delta * 0.58 + luminance_delta * 0.22 + structure_delta * 0.20
        )
        adaptive = float(np.quantile(score, np.clip(0.72 + threshold * 0.22, 0.78, 0.92)))
        raw_mask = score >= adaptive
        mask_image = Image.fromarray((raw_mask * 255).astype(np.uint8), mode="L")
        mask_image = mask_image.filter(ImageFilter.MedianFilter(3)).filter(
            ImageFilter.MaxFilter(3)
        )
        mask = np.asarray(mask_image, dtype=np.uint8) > 0
        confidence = np.clip((score - adaptive) / max(1e-6, 1.0 - adaptive), 0.0, 1.0)
        uncertainty = np.clip(1.0 - np.abs(score - adaptive) / 0.24, 0.0, 1.0)
        colour = np.zeros_like(after)
        colour[mask] = np.asarray(PALETTE["change"], dtype=np.float32) / 255.0
        coverage = float(mask.mean())
        features = self._features_from_mask(mask, "change")
        return {
            "mask": mask,
            "colour": colour,
            "alpha": mask.astype(np.float32) * 0.68,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "features": features,
            "metrics": {
                "predicted_change_pct": round(coverage * 100, 2),
                "mean_confidence_proxy": round(
                    float(confidence[mask].mean()) if mask.any() else 0.0, 3
                ),
                "mean_uncertainty_proxy": round(float(uncertainty.mean()), 3),
                "registration_shift_x_px": shift_x,
                "registration_shift_y_px": shift_y,
                "region_count": len(features["features"]),
            },
            "legend": [
                {"label": "预测变化", "colour": "#ef5475", "share": round(coverage, 4)},
                {"label": "稳定区域", "colour": "#25304a", "share": round(1 - coverage, 4)},
            ],
            "summary": (
                "结果来自小范围平移校正、辐射归一化与多线索差异融合；"
                "它比简单像素差更稳健，但仍需用同区域真值评测。"
            ),
        }

    @staticmethod
    def _estimate_translation(
        before: np.ndarray, after: np.ndarray, max_shift: int = 6
    ) -> tuple[int, int]:
        height, width = before.shape[:2]
        scale = min(1.0, 256 / max(height, width))
        if scale < 1.0:
            size = (max(1, round(width * scale)), max(1, round(height * scale)))
            before_small = np.asarray(
                Image.fromarray((before * 255).astype(np.uint8)).resize(
                    size, Image.Resampling.BILINEAR
                ),
                dtype=np.float32,
            ).mean(axis=2)
            after_small = np.asarray(
                Image.fromarray((after * 255).astype(np.uint8)).resize(
                    size, Image.Resampling.BILINEAR
                ),
                dtype=np.float32,
            ).mean(axis=2)
        else:
            before_small = before.mean(axis=2) * 255
            after_small = after.mean(axis=2) * 255

        best = (float("inf"), 0, 0)
        small_height, small_width = before_small.shape
        bounded_shift = min(max_shift, max(1, min(small_height, small_width) // 8))
        for shift_y in range(-bounded_shift, bounded_shift + 1):
            for shift_x in range(-bounded_shift, bounded_shift + 1):
                before_y, after_y = DemoInterpretationEngine._overlap_slices(
                    small_height, shift_y
                )
                before_x, after_x = DemoInterpretationEngine._overlap_slices(
                    small_width, shift_x
                )
                difference = np.mean(
                    np.abs(
                        before_small[before_y, before_x]
                        - after_small[after_y, after_x]
                    )
                )
                candidate = (float(difference), shift_y, shift_x)
                if candidate < best:
                    best = candidate
        return round(best[1] / scale), round(best[2] / scale)

    @staticmethod
    def _overlap_slices(length: int, shift: int) -> tuple[slice, slice]:
        if shift >= 0:
            return slice(0, length - shift), slice(shift, length)
        return slice(-shift, length), slice(0, length + shift)

    @classmethod
    def _shift_image(
        cls, image: np.ndarray, shift_y: int, shift_x: int, *, fill: np.ndarray
    ) -> np.ndarray:
        height, width = image.shape[:2]
        shifted = fill.copy()
        before_y, after_y = cls._overlap_slices(height, shift_y)
        before_x, after_x = cls._overlap_slices(width, shift_x)
        shifted[after_y, after_x] = image[before_y, before_x]
        return shifted

    def _land_cover(self, image: np.ndarray) -> dict[str, Any]:
        red, green, blue = image[..., 0], image[..., 1], image[..., 2]
        brightness = image.mean(axis=2)
        saturation = image.max(axis=2) - image.min(axis=2)
        water = blue - 0.55 * red - 0.30 * green + (0.40 - brightness) * 0.35
        vegetation = green - 0.72 * red - 0.18 * blue + saturation * 0.30
        built = brightness * 0.55 - saturation * 0.75 + self._gradient(brightness) * 0.9
        bare = red * 0.38 + green * 0.28 - blue * 0.12 + saturation * 0.18
        scores = np.stack([water, vegetation, built, bare], axis=-1)
        labels = np.argmax(scores, axis=-1)
        ordered = np.sort(scores, axis=-1)
        confidence = self._normalise(ordered[..., -1] - ordered[..., -2])
        uncertainty = 1.0 - confidence
        colours = (
            np.asarray(
                [
                    PALETTE["water"],
                    PALETTE["vegetation"],
                    PALETTE["built_up"],
                    PALETTE["bare_land"],
                ],
                dtype=np.float32,
            )
            / 255.0
        )
        colour = colours[labels]
        alpha = np.full(labels.shape, 0.58, dtype=np.float32)
        shares = [(labels == index).mean() for index in range(4)]
        labels_cn = ["水体", "植被", "建成区", "裸地/其他"]
        colour_hex = ["#3c95ff", "#3bcb89", "#f47662", "#c4a675"]
        legend = [
            {"label": label, "colour": colour_hex[index], "share": round(float(shares[index]), 4)}
            for index, label in enumerate(labels_cn)
        ]
        features = self._features_from_mask(labels == 2, "built_up")
        return {
            "mask": labels == 2,
            "colour": colour,
            "alpha": alpha,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "features": features,
            "metrics": {
                "built_up_pct": round(float(shares[2]) * 100, 2),
                "vegetation_pct": round(float(shares[1]) * 100, 2),
                "mean_confidence_proxy": round(float(confidence.mean()), 3),
                "class_count": 4,
            },
            "legend": legend,
            "summary": "四类结果来自透明 RGB 规则基线；多光谱模型接入后可复用相同实验与审计链路。",
        }

    def _road_extraction(self, image: np.ndarray, threshold: float) -> dict[str, Any]:
        brightness = image.mean(axis=2)
        saturation = image.max(axis=2) - image.min(axis=2)
        vegetation = image[..., 1] - image[..., 0]
        edge = self._normalise(self._gradient(brightness))
        road_score = self._normalise(
            brightness * 0.48 - saturation * 0.42 - np.maximum(vegetation, 0) * 0.35 + edge * 0.24
        )
        adaptive = float(np.quantile(road_score, np.clip(0.62 + threshold * 0.18, 0.66, 0.84)))
        mask_image = Image.fromarray((road_score >= adaptive).astype(np.uint8) * 255, mode="L")
        mask_image = mask_image.filter(ImageFilter.MedianFilter(3))
        mask = np.asarray(mask_image, dtype=np.uint8) > 0
        confidence = np.clip((road_score - adaptive) / max(1e-6, 1 - adaptive), 0, 1)
        uncertainty = np.clip(1 - np.abs(road_score - adaptive) / 0.24, 0, 1)
        colour = np.zeros_like(image)
        colour[mask] = np.asarray(PALETTE["road"], dtype=np.float32) / 255.0
        coverage = float(mask.mean())
        features = self._features_from_mask(mask, "road")
        return {
            "mask": mask,
            "colour": colour,
            "alpha": mask.astype(np.float32) * 0.68,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "features": features,
            "metrics": {
                "predicted_road_pct": round(coverage * 100, 2),
                "mean_confidence_proxy": round(
                    float(confidence[mask].mean()) if mask.any() else 0, 3
                ),
                "candidate_region_count": len(features["features"]),
            },
            "legend": [
                {"label": "道路候选", "colour": "#ffbe4f", "share": round(coverage, 4)},
                {"label": "背景", "colour": "#25304a", "share": round(1 - coverage, 4)},
            ],
            "summary": "道路候选由亮度、饱和度和边缘联合基线产生，适合演示低置信度复核闭环。",
        }

    def _object_detection(self, image: np.ndarray) -> dict[str, Any]:
        height, width = image.shape[:2]
        gray = image.mean(axis=2)
        edge = self._normalise(self._gradient(gray))
        tile = max(20, min(height, width) // 12)
        candidates: list[tuple[float, tuple[int, int, int, int]]] = []
        for y in range(0, height - tile + 1, tile):
            for x in range(0, width - tile + 1, tile):
                patch = gray[y : y + tile, x : x + tile]
                patch_edge = edge[y : y + tile, x : x + tile]
                saliency = float(patch.std() * 0.58 + patch_edge.mean() * 0.42)
                candidates.append((saliency, (x, y, min(width, x + tile), min(height, y + tile))))
        candidates.sort(reverse=True, key=lambda item: item[0])
        boxes: list[tuple[float, tuple[int, int, int, int]]] = []
        for score, box in candidates:
            if all(self._intersection_over_union(box, kept[1]) < 0.18 for kept in boxes):
                boxes.append((score, box))
            if len(boxes) == 6:
                break
        raw_scores = np.asarray([item[0] for item in boxes], dtype=np.float32)
        if raw_scores.size:
            minimum, maximum = float(raw_scores.min()), float(raw_scores.max())
            normalised = (raw_scores - minimum) / max(maximum - minimum, 1e-6)
            normalised = 0.56 + normalised * 0.38
        else:
            normalised = np.asarray([], dtype=np.float32)
        mask = np.zeros((height, width), dtype=bool)
        colour = np.zeros_like(image)
        features = []
        for index, ((_, box), score) in enumerate(zip(boxes, normalised, strict=False)):
            x0, y0, x1, y1 = box
            mask[y0:y1, x0:x1] = True
            colour[y0:y1, x0:x1] = np.asarray(PALETTE["change"], dtype=np.float32) / 255.0
            features.append(
                self._bbox_feature(box, "candidate", float(score), index, height=height)
            )
        confidence = np.zeros((height, width), dtype=np.float32)
        for (_, box), score in zip(boxes, normalised, strict=False):
            x0, y0, x1, y1 = box
            confidence[y0:y1, x0:x1] = score
        uncertainty = np.where(mask, 1 - confidence, 0.15).astype(np.float32)
        overlay_base = Image.fromarray((image * 255).astype(np.uint8), mode="RGB")
        draw = ImageDraw.Draw(overlay_base)
        for index, ((_, box), score) in enumerate(zip(boxes, normalised, strict=False), start=1):
            draw.rectangle(box, outline=PALETTE["change"], width=max(2, width // 360))
            draw.text((box[0] + 5, box[1] + 4), f"C{index} {score:.2f}", fill=(255, 255, 255))
        outlined = np.asarray(overlay_base, dtype=np.float32) / 255.0
        return {
            "mask": mask,
            "colour": outlined,
            "alpha": np.ones((height, width), dtype=np.float32),
            "confidence": confidence,
            "uncertainty": uncertainty,
            "features": {"type": "FeatureCollection", "features": features},
            "metrics": {
                "candidate_count": len(boxes),
                "mean_saliency_score": round(float(normalised.mean()) if normalised.size else 0, 3),
                "review_required": len(boxes),
            },
            "legend": [{"label": "待复核候选框", "colour": "#ef5475", "share": 1.0}],
            "summary": "候选框用于验证检测、筛选与 GeoJSON 导出链路，不代表已训练类别模型的预测。",
        }

    @staticmethod
    def _blend(base: Image.Image, colour: np.ndarray, alpha: np.ndarray) -> Image.Image:
        base_array = np.asarray(base, dtype=np.float32) / 255.0
        if colour.shape != base_array.shape:
            raise ValueError("Overlay and base image dimensions differ")
        alpha_3d = np.clip(alpha[..., None], 0, 1)
        mixed = base_array * (1 - alpha_3d) + colour * alpha_3d
        return Image.fromarray((np.clip(mixed, 0, 1) * 255).astype(np.uint8), mode="RGB")

    @staticmethod
    def _uncertainty_image(values: np.ndarray) -> Image.Image:
        values = np.clip(values, 0, 1)
        cold = np.asarray([30, 46, 79], dtype=np.float32)
        hot = np.asarray([255, 177, 74], dtype=np.float32)
        rgb = cold + values[..., None] * (hot - cold)
        return Image.fromarray(rgb.astype(np.uint8), mode="RGB")

    @staticmethod
    def _histogram(confidence: np.ndarray) -> list[int]:
        hist, _ = np.histogram(np.clip(confidence, 0, 1), bins=10, range=(0, 1))
        return [int(value) for value in hist]

    def _features_from_mask(self, mask: np.ndarray, label: str) -> dict[str, Any]:
        height, width = mask.shape
        tile = max(24, min(height, width) // 14)
        candidates: list[tuple[float, tuple[int, int, int, int]]] = []
        for y in range(0, height, tile):
            for x in range(0, width, tile):
                y1, x1 = min(height, y + tile), min(width, x + tile)
                occupancy = float(mask[y:y1, x:x1].mean())
                if occupancy >= 0.12:
                    candidates.append((occupancy, (x, y, x1, y1)))
        candidates.sort(reverse=True, key=lambda item: item[0])
        features = [
            self._bbox_feature(box, label, score, index, height=height)
            for index, (score, box) in enumerate(candidates[:18])
        ]
        return {
            "type": "FeatureCollection",
            "name": f"terrainterpret-{label}-pixel-coordinates",
            "coordinate_reference": "pixel (origin: top-left)",
            "features": features,
        }

    @staticmethod
    def _bbox_feature(
        box: tuple[int, int, int, int],
        label: str,
        score: float,
        index: int,
        *,
        height: int,
    ) -> dict[str, Any]:
        x0, y0, x1, y1 = box
        coordinates = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
        return {
            "type": "Feature",
            "id": index,
            "properties": {
                "label": label,
                "score_proxy": round(score, 4),
                "pixel_area": (x1 - x0) * (y1 - y0),
                "image_height": height,
            },
            "geometry": {"type": "Polygon", "coordinates": [coordinates]},
        }

    @staticmethod
    def _intersection_over_union(
        first: tuple[int, int, int, int], second: tuple[int, int, int, int]
    ) -> float:
        x0, y0 = max(first[0], second[0]), max(first[1], second[1])
        x1, y1 = min(first[2], second[2]), min(first[3], second[3])
        intersection = max(0, x1 - x0) * max(0, y1 - y0)
        first_area = (first[2] - first[0]) * (first[3] - first[1])
        second_area = (second[2] - second[0]) * (second[3] - second[1])
        return intersection / max(first_area + second_area - intersection, 1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
