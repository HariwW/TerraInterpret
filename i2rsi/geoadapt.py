from __future__ import annotations

import hashlib
import json
import math
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import numpy as np

from .models import (
    AdaptationRequest,
    AdaptationRound,
    AnnotationEvent,
    AnnotationRequest,
    GeoAdaptState,
    JobManifest,
    ReviewCandidate,
    ReviewDecision,
    ReviewStatus,
    TaskType,
)


class GeoAdaptNotFoundError(KeyError):
    pass


class GeoAdaptValidationError(ValueError):
    pass


class AdaptationBackend(Protocol):
    id: str

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]: ...


class ProxyCalibrationBackend:
    """Small deterministic calibration backend for the runnable CPU loop.

    This backend calibrates review proxy scores. It does not claim to fine-tune a
    GeoFM. A future LoRA/Adapter backend can implement the same fit contract once
    real weights, sensor inputs, and labelled datasets are configured.
    """

    id = "proxy-logistic-calibration-v1"

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
        weight = 4.0
        bias = -2.0
        for step in range(800):
            logits = np.clip(weight * scores + bias, -30.0, 30.0)
            probabilities = 1.0 / (1.0 + np.exp(-logits))
            error = probabilities - labels
            learning_rate = 0.35 / (1.0 + step / 240.0)
            weight -= learning_rate * (float(np.mean(error * scores)) + 0.002 * weight)
            bias -= learning_rate * float(np.mean(error))
        return round(weight, 8), round(bias, 8)


class GeoAdaptService:
    def __init__(self, root: Path, backend: AdaptationBackend | None = None) -> None:
        self.root = root
        self.candidates_path = root / "review_candidates.json"
        self.events_root = root / "annotation_events"
        self.rounds_root = root / "adaptation_rounds"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_root.mkdir(parents=True, exist_ok=True)
        self.rounds_root.mkdir(parents=True, exist_ok=True)
        self.backend = backend or ProxyCalibrationBackend()
        self._lock = threading.RLock()
        self._candidates: dict[str, ReviewCandidate] = {}
        self._events: list[AnnotationEvent] = []
        self._rounds: list[AdaptationRound] = []
        self._load()

    def ingest_job(
        self, manifest: JobManifest, features: dict[str, object]
    ) -> list[ReviewCandidate]:
        if manifest.status.value != "succeeded":
            raise GeoAdaptValidationError("Only succeeded jobs can enter the review queue")
        width = int(manifest.metrics.get("width_px", 0))
        height = int(manifest.metrics.get("height_px", 0))
        if width <= 0 or height <= 0:
            raise GeoAdaptValidationError("Job image dimensions are unavailable")

        raw_features = features.get("features", [])
        if not isinstance(raw_features, list):
            raise GeoAdaptValidationError("Feature collection is invalid")
        now = datetime.now(UTC)
        created: list[ReviewCandidate] = []
        with self._lock:
            for index, raw_feature in enumerate(raw_features):
                if not isinstance(raw_feature, dict):
                    continue
                properties = raw_feature.get("properties", {})
                geometry = raw_feature.get("geometry", {})
                if not isinstance(properties, dict) or not isinstance(geometry, dict):
                    continue
                feature_id = str(raw_feature.get("id", index))
                candidate_id = hashlib.sha256(f"{manifest.id}:{feature_id}".encode()).hexdigest()[
                    :24
                ]
                if candidate_id in self._candidates:
                    continue
                proxy_score = self._normalise_score(properties.get("score_proxy", 0.5))
                suggested_label = str(properties.get("label", "candidate"))[:80]
                uncertainty = self._uncertainty(manifest.task, manifest.model_id, proxy_score)
                candidate = ReviewCandidate(
                    id=candidate_id,
                    job_id=manifest.id,
                    task=manifest.task,
                    model_id=manifest.model_id,
                    feature_id=feature_id,
                    suggested_label=suggested_label,
                    geometry=self._validate_geometry(geometry, width, height),
                    image_width=width,
                    image_height=height,
                    proxy_score=proxy_score,
                    uncertainty_score=uncertainty,
                    created_at=now,
                    updated_at=now,
                )
                self._candidates[candidate.id] = candidate
                created.append(candidate.model_copy(deep=True))
            self._persist_candidates()
        return created

    def list_reviews(
        self,
        *,
        status: ReviewStatus | None = ReviewStatus.PENDING,
        task: TaskType | None = None,
        job_id: str | None = None,
        limit: int = 20,
    ) -> list[ReviewCandidate]:
        with self._lock:
            pool = [
                candidate.model_copy(deep=True)
                for candidate in self._candidates.values()
                if (status is None or candidate.status is status)
                and (task is None or candidate.task is task)
                and (job_id is None or candidate.job_id == job_id)
            ]
        if status is ReviewStatus.PENDING or status is None:
            return self._rank_candidates(pool)[:limit]
        pool.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return pool[:limit]

    def get_review(self, candidate_id: str) -> ReviewCandidate:
        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise GeoAdaptNotFoundError(candidate_id)
            return candidate.model_copy(deep=True)

    def annotate(self, candidate_id: str, request: AnnotationRequest) -> AnnotationEvent:
        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise GeoAdaptNotFoundError(candidate_id)
            if request.decision is ReviewDecision.CORRECT and not (
                request.label or request.geometry
            ):
                raise GeoAdaptValidationError(
                    "A correction requires a replacement label or geometry"
                )

            if request.decision is ReviewDecision.REJECT:
                label = request.label or "background"
            else:
                label = request.label or candidate.suggested_label
            geometry = self._validate_geometry(
                request.geometry or candidate.geometry,
                candidate.image_width,
                candidate.image_height,
            )
            previous = self._latest_event(candidate_id)
            candidate_version = candidate.annotation_version + 1
            task_event_count = sum(event.task is candidate.task for event in self._events) + 1
            dataset_version = f"geoadapt-{candidate.task.value}-v{task_event_count:04d}"
            now = datetime.now(UTC)
            event_id = uuid.uuid4().hex
            event_payload = {
                "id": event_id,
                "candidate_id": candidate.id,
                "job_id": candidate.job_id,
                "task": candidate.task.value,
                "decision": request.decision.value,
                "label": label,
                "geometry": geometry,
                "notes": request.notes,
                "reviewer": request.reviewer,
                "candidate_version": candidate_version,
                "dataset_version": dataset_version,
                "parent_event_id": previous.id if previous else None,
                "created_at": now.isoformat(),
            }
            event = AnnotationEvent(
                **event_payload,
                sha256=self._digest(event_payload),
            )
            self._write_new_json(
                self.events_root / f"{event.id}.json", event.model_dump(mode="json")
            )
            self._events.append(event)
            candidate.status = {
                ReviewDecision.ACCEPT: ReviewStatus.ACCEPTED,
                ReviewDecision.REJECT: ReviewStatus.REJECTED,
                ReviewDecision.CORRECT: ReviewStatus.CORRECTED,
            }[request.decision]
            candidate.annotation_version = candidate_version
            candidate.updated_at = now
            self._persist_candidates()
            return event.model_copy(deep=True)

    def list_annotations(
        self, *, task: TaskType | None = None, limit: int = 100
    ) -> list[AnnotationEvent]:
        with self._lock:
            events = [
                event.model_copy(deep=True)
                for event in self._events
                if task is None or event.task is task
            ]
        events.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return events[:limit]

    def create_adaptation(self, request: AdaptationRequest) -> AdaptationRound:
        with self._lock:
            latest_events = self._latest_events_for_model(request.task, request.model_id)
            if len(latest_events) < request.min_samples:
                raise GeoAdaptValidationError(
                    f"At least {request.min_samples} reviewed samples are required"
                )
            candidates = [self._candidates[event.candidate_id] for event in latest_events]
            labels = np.asarray(
                [self._event_label(event) for event in latest_events], dtype=np.float64
            )
            positive_count = int(labels.sum())
            negative_count = int(labels.size - positive_count)
            if positive_count == 0 or negative_count == 0:
                raise GeoAdaptValidationError(
                    "Adaptation requires both positive and rejected/background reviews"
                )
            scores = np.asarray(
                [candidate.proxy_score for candidate in candidates], dtype=np.float64
            )
            weight, bias = self.backend.fit(scores, labels)
            raw_brier = float(np.mean((scores - labels) ** 2))
            calibrated = self._sigmoid(weight * scores + bias)
            calibrated_brier = float(np.mean((calibrated - labels) ** 2))
            annotation_digest = hashlib.sha256(
                "".join(sorted(event.sha256 for event in latest_events)).encode()
            ).hexdigest()
            now = datetime.now(UTC)
            latest_dataset = max(
                latest_events, key=lambda event: (event.created_at, event.id)
            ).dataset_version
            round_result = AdaptationRound(
                id=uuid.uuid4().hex,
                task=request.task,
                model_id=request.model_id,
                method=self.backend.id,
                sample_count=len(latest_events),
                positive_count=positive_count,
                negative_count=negative_count,
                weight=weight,
                bias=bias,
                brier_before=round(raw_brier, 8),
                brier_after=round(calibrated_brier, 8),
                annotation_sha256=annotation_digest,
                dataset_version=latest_dataset,
                created_at=now,
                claim_boundary=(
                    "Calibrates transparent proxy scores from reviewed candidates; "
                    "this is not GeoFM or LoRA weight fine-tuning."
                ),
            )
            self._write_new_json(
                self.rounds_root / f"{round_result.id}.json",
                round_result.model_dump(mode="json"),
            )
            self._rounds.append(round_result)
            self._refresh_pending_uncertainty(request.task, request.model_id)
            self._persist_candidates()
            return round_result.model_copy(deep=True)

    def list_adaptations(
        self, *, task: TaskType | None = None, limit: int = 50
    ) -> list[AdaptationRound]:
        with self._lock:
            rounds = [
                item.model_copy(deep=True)
                for item in self._rounds
                if task is None or item.task is task
            ]
        rounds.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return rounds[:limit]

    def state(self) -> GeoAdaptState:
        with self._lock:
            pending = sum(
                candidate.status is ReviewStatus.PENDING for candidate in self._candidates.values()
            )
            calibrators = {
                f"{item.task.value}:{item.model_id}": item.id for item in self._latest_rounds()
            }
            return GeoAdaptState(
                review_candidates=len(self._candidates),
                pending_reviews=pending,
                annotation_events=len(self._events),
                adaptation_rounds=len(self._rounds),
                loop_complete=bool(self._events and self._rounds),
                active_calibrators=calibrators,
                capabilities={
                    "uncertainty_diversity_acquisition": "implemented",
                    "append_only_human_review": "implemented",
                    "versioned_label_lineage": "implemented",
                    "proxy_calibration_feedback": "implemented",
                    "geofm_peft": "backend contract only; weights/data not configured",
                    "multisensor_modality_dropout": "research protocol only",
                },
            )

    def _rank_candidates(self, candidates: Sequence[ReviewCandidate]) -> list[ReviewCandidate]:
        remaining = list(candidates)
        selected: list[ReviewCandidate] = []
        descriptors: dict[str, np.ndarray] = {
            candidate.id: self._descriptor(candidate) for candidate in remaining
        }
        while remaining:
            scored: list[tuple[float, str, float, ReviewCandidate]] = []
            for candidate in remaining:
                if not selected:
                    diversity = 1.0
                else:
                    diversity = min(
                        float(
                            np.linalg.norm(descriptors[candidate.id] - descriptors[item.id])
                            / math.sqrt(5.0)
                        )
                        for item in selected
                    )
                diversity = float(np.clip(diversity, 0.0, 1.0))
                acquisition = 0.72 * candidate.uncertainty_score + 0.28 * diversity
                scored.append((acquisition, candidate.id, diversity, candidate))
            _, _, diversity, chosen = max(scored, key=lambda item: (item[0], item[1]))
            chosen.diversity_score = round(diversity, 6)
            chosen.acquisition_score = round(0.72 * chosen.uncertainty_score + 0.28 * diversity, 6)
            selected.append(chosen)
            remaining.remove(chosen)
        return selected

    def _descriptor(self, candidate: ReviewCandidate) -> np.ndarray:
        coordinates = candidate.geometry["coordinates"][0]
        xs = [float(point[0]) for point in coordinates]
        ys = [float(point[1]) for point in coordinates]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        return np.asarray(
            [
                ((min(xs) + max(xs)) / 2.0) / candidate.image_width,
                ((min(ys) + max(ys)) / 2.0) / candidate.image_height,
                width / candidate.image_width,
                height / candidate.image_height,
                candidate.proxy_score,
            ],
            dtype=np.float64,
        )

    def _uncertainty(self, task: TaskType, model_id: str, proxy_score: float) -> float:
        round_result = self._latest_round(task, model_id)
        probability = proxy_score
        if round_result is not None:
            probability = float(
                self._sigmoid(round_result.weight * proxy_score + round_result.bias)
            )
        return round(float(1.0 - abs(probability - 0.5) * 2.0), 6)

    def _refresh_pending_uncertainty(self, task: TaskType, model_id: str) -> None:
        for candidate in self._candidates.values():
            if (
                candidate.task is task
                and candidate.model_id == model_id
                and candidate.status is ReviewStatus.PENDING
            ):
                candidate.uncertainty_score = self._uncertainty(
                    task, model_id, candidate.proxy_score
                )
                candidate.updated_at = datetime.now(UTC)

    def _latest_round(self, task: TaskType, model_id: str) -> AdaptationRound | None:
        matches = [item for item in self._rounds if item.task is task and item.model_id == model_id]
        return max(matches, key=lambda item: (item.created_at, item.id), default=None)

    def _latest_rounds(self) -> list[AdaptationRound]:
        latest: dict[tuple[TaskType, str], AdaptationRound] = {}
        for item in self._rounds:
            key = (item.task, item.model_id)
            previous = latest.get(key)
            if previous is None or (item.created_at, item.id) > (
                previous.created_at,
                previous.id,
            ):
                latest[key] = item
        return list(latest.values())

    def _latest_event(self, candidate_id: str) -> AnnotationEvent | None:
        matches = [event for event in self._events if event.candidate_id == candidate_id]
        return max(
            matches,
            key=lambda event: (event.candidate_version, event.created_at, event.id),
            default=None,
        )

    def _latest_events_for_model(self, task: TaskType, model_id: str) -> list[AnnotationEvent]:
        latest: dict[str, AnnotationEvent] = {}
        for event in self._events:
            candidate = self._candidates.get(event.candidate_id)
            if candidate is None or candidate.task is not task or candidate.model_id != model_id:
                continue
            previous = latest.get(event.candidate_id)
            if previous is None or event.candidate_version > previous.candidate_version:
                latest[event.candidate_id] = event
        return sorted(latest.values(), key=lambda event: event.candidate_id)

    @staticmethod
    def _event_label(event: AnnotationEvent) -> float:
        if event.decision is ReviewDecision.REJECT:
            return 0.0
        return 0.0 if event.label.strip().lower() in {"background", "negative"} else 1.0

    @staticmethod
    def _normalise_score(value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.5
        return round(float(np.clip(score, 0.0, 1.0)), 6)

    @staticmethod
    def _sigmoid(value: float | np.ndarray) -> float | np.ndarray:
        clipped = np.clip(value, -30.0, 30.0)
        return 1.0 / (1.0 + np.exp(-clipped))

    @staticmethod
    def _validate_geometry(
        geometry: dict[str, object], width: int, height: int
    ) -> dict[str, object]:
        if geometry.get("type") != "Polygon":
            raise GeoAdaptValidationError("Review geometry must be a GeoJSON Polygon")
        rings = geometry.get("coordinates")
        if not isinstance(rings, list) or not rings or not isinstance(rings[0], list):
            raise GeoAdaptValidationError("Review polygon coordinates are invalid")
        ring = rings[0]
        if len(ring) < 4:
            raise GeoAdaptValidationError("Review polygon requires at least four points")
        clean_ring: list[list[float]] = []
        for point in ring:
            if not isinstance(point, list) or len(point) < 2:
                raise GeoAdaptValidationError("Review polygon point is invalid")
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError) as exc:
                raise GeoAdaptValidationError("Review polygon point is not numeric") from exc
            if not (math.isfinite(x) and math.isfinite(y)):
                raise GeoAdaptValidationError("Review polygon point must be finite")
            if x < 0 or y < 0 or x > width or y > height:
                raise GeoAdaptValidationError("Review polygon falls outside the source image")
            clean_ring.append([round(x, 4), round(y, 4)])
        if clean_ring[0] != clean_ring[-1]:
            raise GeoAdaptValidationError("Review polygon ring must be closed")
        return {"type": "Polygon", "coordinates": [clean_ring]}

    @staticmethod
    def _digest(payload: object) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _write_new_json(path: Path, payload: object) -> None:
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
        except FileExistsError as exc:  # UUID collision or attempted mutation
            raise GeoAdaptValidationError("Immutable event already exists") from exc

    def _persist_candidates(self) -> None:
        target = self.candidates_path
        temporary = self.root / ".review_candidates.tmp"
        payload = [
            candidate.model_dump(mode="json")
            for candidate in sorted(self._candidates.values(), key=lambda item: item.id)
        ]
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def _load(self) -> None:
        if self.candidates_path.is_file():
            try:
                payload = json.loads(self.candidates_path.read_text(encoding="utf-8"))
                self._candidates = {
                    item["id"]: ReviewCandidate.model_validate(item) for item in payload
                }
            except (OSError, ValueError, KeyError, TypeError):
                self._candidates = {}
        for path in sorted(self.events_root.glob("*.json")):
            try:
                event = AnnotationEvent.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self._events.append(event)
        for path in sorted(self.rounds_root.glob("*.json")):
            try:
                round_result = AdaptationRound.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self._rounds.append(round_result)
