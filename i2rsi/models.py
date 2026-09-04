from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

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


class WorkflowStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_GROUND_TRUTH = "awaiting_ground_truth"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


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


class InferenceParameterSpec(BaseModel):
    key: str
    label: str
    description: str
    default: float
    minimum: float
    maximum: float
    step: float = 0.01


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
    backend: str = "lite"
    runtime: str = "builtin"
    weight_source: str | None = None
    license: str = "Project source license"
    recommended_device: str = "CPU"
    inference_parameters: list[InferenceParameterSpec] = Field(default_factory=list)


class ModelRuntimeStatus(BaseModel):
    model_id: str
    ready: bool
    backend: str
    runtime: str
    device: str
    weights_cached: bool = False
    reason: str | None = None
    setup_hint: str | None = None


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


class AgentStatus(BaseModel):
    enabled: bool
    installed: bool
    ready: bool
    package_version: str | None = None
    provider: str
    model: str | None = None
    safe_mode: str
    setup_hint: str | None = None


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)
    current_job_id: str | None = Field(default=None, max_length=64)
    allow_actions: bool = False


class AgentChatResponse(BaseModel):
    conversation_id: str
    answer: str
    executed_tools: list[str]
    cancelled_tools: list[str]
    action_mode: bool


class AgentMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class AgentMessage(BaseModel):
    id: str
    role: AgentMessageRole
    content: str
    created_at: datetime
    executed_tools: list[str] = Field(default_factory=list)
    cancelled_tools: list[str] = Field(default_factory=list)
    allow_actions: bool = False


class AgentConversation(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    archived: bool = False
    messages: list[AgentMessage] = Field(default_factory=list)


class AgentConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    archived: bool
    message_count: int
    preview: str = ""


class AgentConversationCreateRequest(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=80)


class AgentConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    archived: bool | None = None


class DataAssetRecord(BaseModel):
    role: str
    name: str
    relative_path: str | None = None
    media_type: str
    bytes: int
    sha256: str
    width_px: int
    height_px: int


class DatasetRecord(BaseModel):
    id: str
    version: str
    name: str
    description: str = ""
    task_hint: TaskType | None = None
    coordinate_space: str
    source: str
    layout: Literal["single", "paired", "folder"] = "single"
    sample_count: int = Field(default=1, ge=1)
    assets: list[DataAssetRecord]
    created_at: datetime


class DatasetRunRequest(BaseModel):
    task: TaskType
    model_id: str = Field(min_length=1, max_length=120)
    threshold: float | None = Field(default=None, ge=0.05, le=0.95)


class EvaluationReport(BaseModel):
    id: str
    job_id: str
    task: TaskType
    model_id: str
    metric_suite: str
    ground_truth_name: str
    ground_truth_sha256: str
    prediction_sha256: str
    positive_threshold: int
    metrics: dict[str, float | None]
    confusion: dict[str, int]
    pixel_count: int
    created_at: datetime
    claim_scope: str


class WorkflowCreateRequest(BaseModel):
    name: str = Field(default="遥感解译编排", min_length=1, max_length=120)
    dataset_id: str = Field(min_length=1, max_length=64)
    task: TaskType
    model_ids: list[str] = Field(default_factory=list, max_length=4)
    model_parameters: dict[str, dict[str, float]] = Field(default_factory=dict)
    threshold: float | None = Field(default=None, ge=0.05, le=0.95, exclude=True)


class WorkflowStep(BaseModel):
    id: str
    kind: str
    label: str
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    model_id: str | None = None
    job_id: str | None = None
    evaluation_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class WorkflowRecord(BaseModel):
    id: str
    name: str
    dataset_id: str
    dataset_version: str
    task: TaskType
    model_ids: list[str]
    model_parameters: dict[str, dict[str, float]] = Field(default_factory=dict)
    status: WorkflowStatus
    steps: list[WorkflowStep]
    job_ids: list[str] = Field(default_factory=list)
    evaluation_ids: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    error: str | None = None
