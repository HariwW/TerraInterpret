from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from .engine import sha256_file
from .models import EvaluationReport, JobStatus, TaskType
from .service import JobService


class EvaluationNotFoundError(KeyError):
    pass


class EvaluationValidationError(ValueError):
    pass


class EvaluationService:
    """Persisted ground-truth evaluation for binary segmentation outputs."""

    SUPPORTED_TASKS = frozenset({TaskType.CHANGE_DETECTION, TaskType.ROAD_EXTRACTION})

    def __init__(self, root: Path, jobs: JobService) -> None:
        self.root = root
        self.jobs = jobs
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._reports: dict[str, EvaluationReport] = {}
        self._load_existing()

    def create(
        self,
        *,
        job_id: str,
        ground_truth: bytes,
        ground_truth_name: str,
        positive_threshold: int = 127,
    ) -> EvaluationReport:
        job = self.jobs.get_job(job_id)
        if job.status is not JobStatus.SUCCEEDED:
            raise EvaluationValidationError("Only succeeded runs can be evaluated")
        if job.task not in self.SUPPORTED_TASKS:
            raise EvaluationValidationError(
                "This metric suite supports change detection and road extraction only"
            )
        if not 1 <= positive_threshold <= 254:
            raise EvaluationValidationError("Positive threshold must be between 1 and 254")

        prediction_path = self.jobs.jobs_root / job_id / "outputs" / "mask.png"
        if not prediction_path.is_file():
            raise EvaluationValidationError("The run does not contain a prediction mask")
        with Image.open(prediction_path) as prediction_image:
            prediction = np.asarray(prediction_image.convert("L")) > 127
        truth_image = self._decode_ground_truth(ground_truth)
        if truth_image.size != (prediction.shape[1], prediction.shape[0]):
            raise EvaluationValidationError(
                "Ground-truth dimensions must match the prediction mask"
            )
        truth_values = np.asarray(truth_image, dtype=np.uint8)
        truth = truth_values > positive_threshold

        tp = int(np.logical_and(prediction, truth).sum())
        tn = int(np.logical_and(~prediction, ~truth).sum())
        fp = int(np.logical_and(prediction, ~truth).sum())
        fn = int(np.logical_and(~prediction, truth).sum())
        precision = self._divide(tp, tp + fp)
        recall = self._divide(tp, tp + fn)
        metrics = {
            "iou": self._divide(tp, tp + fp + fn),
            "f1": self._divide(2 * tp, 2 * tp + fp + fn),
            "precision": precision,
            "recall": recall,
            "accuracy": self._divide(tp + tn, tp + tn + fp + fn),
            "specificity": self._divide(tn, tn + fp),
        }

        evaluation_id = uuid.uuid4().hex
        evaluation_dir = self.root / evaluation_id
        evaluation_dir.mkdir(parents=True, exist_ok=False)
        normalized_truth = evaluation_dir / "ground_truth.png"
        Image.fromarray((truth * 255).astype(np.uint8), mode="L").save(
            normalized_truth,
            optimize=True,
        )
        report = EvaluationReport(
            id=evaluation_id,
            job_id=job.id,
            task=job.task,
            model_id=job.model_id,
            metric_suite="binary-segmentation-v1",
            ground_truth_name=Path(ground_truth_name).name[:160] or "ground_truth.png",
            ground_truth_sha256=sha256_file(normalized_truth),
            prediction_sha256=sha256_file(prediction_path),
            positive_threshold=positive_threshold,
            metrics={
                key: round(value, 6) if value is not None else None
                for key, value in metrics.items()
            },
            confusion={"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            pixel_count=int(prediction.size),
            created_at=datetime.now(UTC),
            claim_scope=(
                "Metrics are valid only for this prediction, uploaded ground truth, "
                "positive-class convention, and metric-suite version. Metrics with "
                "a zero denominator are reported as null rather than zero."
            ),
        )
        with self._lock:
            self._reports[evaluation_id] = report
            self._persist(report)
        return report.model_copy(deep=True)

    def list_reports(self, limit: int = 100) -> list[EvaluationReport]:
        with self._lock:
            reports = sorted(
                self._reports.values(),
                key=lambda item: item.created_at,
                reverse=True,
            )[:limit]
            return [item.model_copy(deep=True) for item in reports]

    def get_report(self, evaluation_id: str) -> EvaluationReport:
        with self._lock:
            report = self._reports.get(evaluation_id)
            if report is None:
                raise EvaluationNotFoundError(evaluation_id)
            return report.model_copy(deep=True)

    def _decode_ground_truth(self, payload: bytes) -> Image.Image:
        if not payload:
            raise EvaluationValidationError("Ground-truth mask is empty")
        if len(payload) > self.jobs.settings.max_upload_bytes:
            raise EvaluationValidationError("Ground-truth mask exceeds the upload limit")
        try:
            with Image.open(BytesIO(payload)) as image:
                if image.format not in {"PNG", "JPEG"}:
                    raise EvaluationValidationError("Ground truth must be a PNG or JPEG image")
                if image.width * image.height > self.jobs.settings.max_image_pixels:
                    raise EvaluationValidationError("Decoded ground truth exceeds the pixel limit")
                return image.convert("L").copy()
        except EvaluationValidationError:
            raise
        except (OSError, UnidentifiedImageError) as exc:
            raise EvaluationValidationError("Ground truth is not a readable image") from exc

    @staticmethod
    def _divide(numerator: float, denominator: float) -> float | None:
        return float(numerator / denominator) if denominator else None

    def _persist(self, report: EvaluationReport) -> None:
        evaluation_dir = self.root / report.id
        target = evaluation_dir / "report.json"
        temporary = evaluation_dir / ".report.tmp"
        temporary.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _load_existing(self) -> None:
        for path in self.root.glob("*/report.json"):
            try:
                report = EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self._reports[report.id] = report
