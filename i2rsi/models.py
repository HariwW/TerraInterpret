from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    CHANGE_DETECTION = "change_detection"
    LAND_COVER = "land_cover"
    OBJECT_DETECTION = "object_detection"
    ROAD_EXTRACTION = "road_extraction"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CORRECTED = "corrected"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECT = "correct"


class Artifact(BaseModel):
    kind: str
    label: str
    url: str
    media_type: str
    sha256: str


class ModelCard(BaseModel):
    id: str
    name: str
    task: TaskType
    family: str
    version: str
    stage: str
    description: str
    strengths: list[str]
    limitations: list[str]
    expected_inputs: list[str]
    reference_metrics: dict[str, float | str] = Field(default_factory=dict)
    metric_scope: str


class JobManifest(BaseModel):
    id: str
    task: TaskType
    model_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    parameters: dict[str, Any]
    inputs: list[dict[str, Any]]
    artifacts: list[Artifact] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    histogram: list[int] = Field(default_factory=list)
    legend: list[dict[str, str | int | float]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    error: str | None = None

    @classmethod
    def queued(
        cls,
        *,
        job_id: str,
        task: TaskType,
        model_id: str,
        parameters: dict[str, Any],
        inputs: list[dict[str, Any]],
    ) -> JobManifest:
        now = datetime.now(UTC)
        return cls(
            id=job_id,
            task=task,
            model_id=model_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            parameters=parameters,
            inputs=inputs,
        )


class HealthResponse(BaseModel):
    status: str
    version: str
    engine: str
    demo_archive: bool
    timestamp: datetime


class DemoScenario(BaseModel):
    id: str
    title: str
    subtitle: str
    task: TaskType
    primary_asset: str
    secondary_asset: str | None = None
    model_id: str


class ReviewCandidate(BaseModel):
    id: str
    job_id: str
    task: TaskType
    model_id: str
    feature_id: str
    suggested_label: str
    geometry: dict[str, Any]
    image_width: int
    image_height: int
    proxy_score: float = Field(ge=0.0, le=1.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    diversity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    acquisition_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: ReviewStatus = ReviewStatus.PENDING
    annotation_version: int = 0
    created_at: datetime
    updated_at: datetime


class AnnotationRequest(BaseModel):
    decision: ReviewDecision
    label: str | None = Field(default=None, max_length=80)
    geometry: dict[str, Any] | None = None
    notes: str = Field(default="", max_length=500)
    reviewer: str = Field(default="local-user", min_length=1, max_length=80)


class AnnotationEvent(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    task: TaskType
    decision: ReviewDecision
    label: str
    geometry: dict[str, Any]
    notes: str
    reviewer: str
    candidate_version: int
    dataset_version: str
    parent_event_id: str | None = None
    created_at: datetime
    sha256: str


class AdaptationRequest(BaseModel):
    task: TaskType
    model_id: str
    min_samples: int = Field(default=4, ge=4, le=10_000)


class AdaptationRound(BaseModel):
    id: str
    task: TaskType
    model_id: str
    method: str
    sample_count: int
    positive_count: int
    negative_count: int
    weight: float
    bias: float
    brier_before: float
    brier_after: float
    annotation_sha256: str
    dataset_version: str
    created_at: datetime
    claim_boundary: str


class GeoAdaptState(BaseModel):
    name: str = "GeoAdapt Loop"
    review_candidates: int
    pending_reviews: int
    annotation_events: int
    adaptation_rounds: int
    loop_complete: bool
    active_calibrators: dict[str, str]
    capabilities: dict[str, str]
