from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .agent_bridge import GeoAgentBridge, GeoAgentIntegrationError
from .catalog import DataCatalogService, DatasetNotFoundError
from .conversations import ConversationNotFoundError, ConversationService
from .evaluation import (
    EvaluationNotFoundError,
    EvaluationService,
    EvaluationValidationError,
)
from .geoadapt import GeoAdaptNotFoundError, GeoAdaptService, GeoAdaptValidationError
from .models import (
    AdaptationRequest,
    AdaptationRound,
    AgentChatRequest,
    AgentChatResponse,
    AgentConversation,
    AgentConversationCreateRequest,
    AgentConversationSummary,
    AgentConversationUpdateRequest,
    AgentStatus,
    AnnotationEvent,
    AnnotationRequest,
    DatasetRecord,
    DatasetRunRequest,
    DemoScenario,
    EvaluationReport,
    GeoAdaptState,
    HealthResponse,
    JobManifest,
    JobStatus,
    ReviewCandidate,
    ReviewStatus,
    TaskType,
    WorkflowCreateRequest,
    WorkflowRecord,
)
from .registry import DEMO_ASSETS, DEMO_SCENARIOS, MODEL_BY_ID, MODEL_CARDS
from .service import JobNotFoundError, JobService
from .settings import Settings
from .workflow import (
    WorkflowNotFoundError,
    WorkflowService,
    WorkflowValidationError,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
    geoadapt = GeoAdaptService(resolved_settings.artifact_root / "geoadapt")
    service = JobService(resolved_settings, geoadapt=geoadapt)
    catalog = DataCatalogService(resolved_settings)
    evaluation = EvaluationService(resolved_settings.artifact_root / "evaluations", service)
    workflow = WorkflowService(
        resolved_settings.artifact_root / "workflows",
        catalog,
        service,
        evaluation,
    )
    conversations = ConversationService(
        resolved_settings.artifact_root / "agent-conversations"
    )
    agent_bridge = GeoAgentBridge(
        resolved_settings,
        service,
        geoadapt,
        catalog,
        evaluation,
        workflow,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        resolved_settings.artifact_root.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(
        title="TerraInterpret GeoAI Workbench API",
        summary="Reproducible remote-sensing interpretation jobs and artifacts",
        description=(
            "V2 separates inference observations from ground-truth evaluation and records "
            "provenance for every run."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.service = service
    app.state.catalog = catalog
    app.state.evaluation = evaluation
    app.state.geoadapt = geoadapt
    app.state.workflow = workflow
    app.state.conversations = conversations
    app.state.agent_bridge = agent_bridge

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'"
        )
        return response

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            engine=service.engine.id,
            demo_archive=resolved_settings.demo_archive.exists(),
            timestamp=datetime.now(UTC),
        )

    @app.get("/api/v1/models", tags=["registry"])
    def models(
        refresh: Annotated[bool, Query()] = False,
    ):  # type: ignore[no-untyped-def]
        statuses = service.engine.statuses(refresh=refresh)
        defaults = {
            task: service.engine.preferred_model_id(task, statuses) for task in TaskType
        }
        items = [
            {
                **card.model_dump(mode="json"),
                "is_default": defaults[card.task] == card.id,
                "runtime_status": statuses[card.id].model_dump(mode="json"),
            }
            for card in MODEL_CARDS
        ]
        return {"items": items, "count": len(items)}

    @app.get("/api/v1/models/{model_id}", tags=["registry"])
    def model_detail(model_id: str):  # type: ignore[no-untyped-def]
        card = MODEL_BY_ID.get(model_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return {
            **card.model_dump(mode="json"),
            "is_default": service.engine.preferred_model_id(card.task) == card.id,
            "runtime_status": service.engine.status(card).model_dump(mode="json"),
        }

    @app.get("/api/v1/data/summary", tags=["data"])
    def data_summary():  # type: ignore[no-untyped-def]
        return catalog.summary(len(DEMO_SCENARIOS))

    @app.get(
        "/api/v1/datasets",
        response_model=list[DatasetRecord],
        tags=["data"],
    )
    def list_datasets(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[DatasetRecord]:
        return catalog.list_datasets(limit)

    @app.post(
        "/api/v1/datasets",
        response_model=DatasetRecord,
        tags=["data"],
    )
    async def create_dataset(
        name: Annotated[str, Form(min_length=1, max_length=120)],
        primary: Annotated[UploadFile, File()],
        description: Annotated[str, Form(max_length=500)] = "",
        task_hint: Annotated[TaskType | None, Form()] = None,
        secondary: Annotated[UploadFile | None, File()] = None,
    ) -> DatasetRecord:
        primary_bytes = await _read_upload(primary, resolved_settings.max_upload_bytes)
        secondary_bytes = (
            await _read_upload(secondary, resolved_settings.max_upload_bytes) if secondary else None
        )
        try:
            return catalog.create_dataset(
                name=name,
                description=description,
                task_hint=task_hint,
                primary=primary_bytes,
                primary_name=primary.filename or "primary.image",
                secondary=secondary_bytes,
                secondary_name=secondary.filename if secondary else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/datasets/folder",
        response_model=DatasetRecord,
        tags=["data"],
    )
    async def create_folder_dataset(
        name: Annotated[str, Form(min_length=1, max_length=120)],
        files: Annotated[list[UploadFile], File()],
        description: Annotated[str, Form(max_length=500)] = "",
        task_hint: Annotated[TaskType | None, Form()] = None,
    ) -> DatasetRecord:
        if len(files) > resolved_settings.max_dataset_files:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Dataset folder exceeds the "
                    f"{resolved_settings.max_dataset_files}-file limit"
                ),
            )
        uploads: list[tuple[str, bytes]] = []
        total_bytes = 0
        for upload in files:
            payload = await _read_upload(upload, resolved_settings.max_upload_bytes)
            total_bytes += len(payload)
            if total_bytes > resolved_settings.max_dataset_bytes:
                limit_mb = resolved_settings.max_dataset_bytes // (1024 * 1024)
                raise HTTPException(
                    status_code=413,
                    detail=f"Dataset folder exceeds the {limit_mb} MB total limit",
                )
            uploads.append((upload.filename or "unnamed.image", payload))
        try:
            return catalog.create_folder_dataset(
                name=name,
                description=description,
                task_hint=task_hint,
                files=uploads,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/datasets/{dataset_id}",
        response_model=DatasetRecord,
        tags=["data"],
    )
    def get_dataset(dataset_id: str) -> DatasetRecord:
        try:
            return catalog.get_dataset(dataset_id)
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Dataset not found") from exc

    @app.post(
        "/api/v1/datasets/{dataset_id}/runs",
        response_model=JobManifest,
        tags=["data", "jobs"],
    )
    def run_dataset(
        dataset_id: str,
        request: DatasetRunRequest,
        background_tasks: BackgroundTasks,
    ) -> JobManifest:
        try:
            dataset = catalog.get_dataset(dataset_id)
            primary, primary_name, secondary, secondary_name = catalog.read_inputs(dataset_id)
            manifest = service.create_job(
                task=request.task,
                model_id=request.model_id,
                primary=primary,
                primary_name=primary_name,
                secondary=secondary,
                secondary_name=secondary_name,
                threshold=request.threshold,
                source=f"dataset:{dataset.id}@{dataset.version}",
            )
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        background_tasks.add_task(service.run_job, manifest.id)
        return manifest

    @app.get("/api/v1/scenarios", response_model=list[DemoScenario], tags=["demo"])
    def scenarios() -> list[DemoScenario]:
        return service.resolved_demo_scenarios()

    @app.get("/api/v1/demo-assets/{asset_id}", tags=["demo"])
    def demo_asset(asset_id: str) -> Response:
        asset = DEMO_ASSETS.get(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Demo asset not found")
        _, media_type = asset
        if not resolved_settings.demo_archive.exists():
            raise HTTPException(status_code=404, detail="Demo archive is unavailable")
        try:
            payload, _ = service.read_demo_asset(asset_id)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="Demo archive is invalid") from exc
        return Response(
            payload,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.post(
        "/api/v1/demo-runs/bootstrap",
        response_model=list[JobManifest],
        tags=["demo"],
    )
    def bootstrap_demo_runs(background_tasks: BackgroundTasks) -> list[JobManifest]:
        try:
            manifests, created_job_ids = service.ensure_demo_jobs()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        for job_id in created_job_ids:
            background_tasks.add_task(service.run_job, job_id)
        return manifests

    @app.post("/api/v1/demo-runs/{scenario_id}", response_model=JobManifest, tags=["demo"])
    def create_demo_run(
        scenario_id: str,
        background_tasks: BackgroundTasks,
        threshold: Annotated[float | None, Query(ge=0.05, le=0.95)] = None,
    ) -> JobManifest:
        try:
            manifest = service.create_demo_job(scenario_id, threshold)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        background_tasks.add_task(service.run_job, manifest.id)
        return manifest

    @app.post("/api/v1/jobs", response_model=JobManifest, tags=["jobs"])
    async def create_job(
        background_tasks: BackgroundTasks,
        task: Annotated[TaskType, Form()],
        model_id: Annotated[str, Form()],
        primary: Annotated[UploadFile, File()],
        secondary: Annotated[UploadFile | None, File()] = None,
        threshold: Annotated[float | None, Form(ge=0.05, le=0.95)] = None,
    ) -> JobManifest:
        primary_bytes = await _read_upload(primary, resolved_settings.max_upload_bytes)
        secondary_bytes = (
            await _read_upload(secondary, resolved_settings.max_upload_bytes) if secondary else None
        )
        try:
            manifest = service.create_job(
                task=task,
                model_id=model_id,
                primary=primary_bytes,
                primary_name=primary.filename or "primary.image",
                secondary=secondary_bytes,
                secondary_name=secondary.filename if secondary else None,
                threshold=threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        background_tasks.add_task(service.run_job, manifest.id)
        return manifest

    @app.get("/api/v1/jobs", response_model=list[JobManifest], tags=["jobs"])
    def list_jobs(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        status: Annotated[JobStatus | None, Query()] = None,
        task: Annotated[TaskType | None, Query()] = None,
        model_id: Annotated[str | None, Query(max_length=120)] = None,
    ) -> list[JobManifest]:
        return service.list_jobs(limit, status=status, task=task, model_id=model_id)

    @app.get("/api/v1/jobs/{job_id}", response_model=JobManifest, tags=["jobs"])
    def get_job(job_id: str) -> JobManifest:
        try:
            return service.get_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get(
        "/api/v1/evaluations",
        response_model=list[EvaluationReport],
        tags=["evaluation"],
    )
    def list_evaluations(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[EvaluationReport]:
        return evaluation.list_reports(limit)

    @app.post(
        "/api/v1/evaluations",
        response_model=EvaluationReport,
        tags=["evaluation"],
    )
    async def create_evaluation(
        job_id: Annotated[str, Form(min_length=1, max_length=64)],
        ground_truth: Annotated[UploadFile, File()],
        positive_threshold: Annotated[int, Form(ge=1, le=254)] = 127,
    ) -> EvaluationReport:
        payload = await _read_upload(ground_truth, resolved_settings.max_upload_bytes)
        try:
            return evaluation.create(
                job_id=job_id,
                ground_truth=payload,
                ground_truth_name=ground_truth.filename or "ground_truth.png",
                positive_threshold=positive_threshold,
            )
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        except EvaluationValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/evaluations/{evaluation_id}",
        response_model=EvaluationReport,
        tags=["evaluation"],
    )
    def get_evaluation(evaluation_id: str) -> EvaluationReport:
        try:
            return evaluation.get_report(evaluation_id)
        except EvaluationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Evaluation not found") from exc

    @app.get(
        "/api/v1/workflows",
        response_model=list[WorkflowRecord],
        tags=["workflows"],
    )
    def list_workflows(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[WorkflowRecord]:
        return workflow.list(limit)

    @app.post(
        "/api/v1/workflows",
        response_model=WorkflowRecord,
        tags=["workflows"],
    )
    def create_workflow(request: WorkflowCreateRequest) -> WorkflowRecord:
        try:
            return workflow.create_plan(request)
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Dataset not found") from exc
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/workflows/{workflow_id}",
        response_model=WorkflowRecord,
        tags=["workflows"],
    )
    def get_workflow(workflow_id: str) -> WorkflowRecord:
        try:
            return workflow.get(workflow_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workflow not found") from exc

    @app.post(
        "/api/v1/workflows/{workflow_id}/execute",
        response_model=WorkflowRecord,
        tags=["workflows"],
    )
    def execute_workflow(
        workflow_id: str,
        background_tasks: BackgroundTasks,
    ) -> WorkflowRecord:
        try:
            record = workflow.queue(workflow_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workflow not found") from exc
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        background_tasks.add_task(workflow.execute, workflow_id)
        return record

    @app.post(
        "/api/v1/workflows/{workflow_id}/evaluations",
        response_model=WorkflowRecord,
        tags=["workflows", "evaluation"],
    )
    async def evaluate_workflow(
        workflow_id: str,
        ground_truth: Annotated[UploadFile, File()],
        positive_threshold: Annotated[int, Form(ge=1, le=254)] = 127,
    ) -> WorkflowRecord:
        payload = await _read_upload(ground_truth, resolved_settings.max_upload_bytes)
        try:
            return workflow.evaluate(
                workflow_id,
                ground_truth=payload,
                ground_truth_name=ground_truth.filename or "ground_truth.png",
                positive_threshold=positive_threshold,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workflow not found") from exc
        except (WorkflowValidationError, EvaluationValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/geoadapt/state",
        response_model=GeoAdaptState,
        tags=["geoadapt"],
    )
    def geoadapt_state() -> GeoAdaptState:
        return geoadapt.state()

    @app.get(
        "/api/v1/geoadapt/reviews",
        response_model=list[ReviewCandidate],
        tags=["geoadapt"],
    )
    def list_geoadapt_reviews(
        status: Annotated[ReviewStatus | None, Query()] = ReviewStatus.PENDING,
        task: Annotated[TaskType | None, Query()] = None,
        job_id: Annotated[str | None, Query(max_length=64)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[ReviewCandidate]:
        return geoadapt.list_reviews(
            status=status,
            task=task,
            job_id=job_id,
            limit=limit,
        )

    @app.get(
        "/api/v1/geoadapt/reviews/{candidate_id}",
        response_model=ReviewCandidate,
        tags=["geoadapt"],
    )
    def get_geoadapt_review(candidate_id: str) -> ReviewCandidate:
        try:
            return geoadapt.get_review(candidate_id)
        except GeoAdaptNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Review candidate not found") from exc

    @app.post(
        "/api/v1/geoadapt/reviews/{candidate_id}/annotations",
        response_model=AnnotationEvent,
        tags=["geoadapt"],
    )
    def annotate_geoadapt_review(candidate_id: str, request: AnnotationRequest) -> AnnotationEvent:
        try:
            return geoadapt.annotate(candidate_id, request)
        except GeoAdaptNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Review candidate not found") from exc
        except GeoAdaptValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/geoadapt/annotations",
        response_model=list[AnnotationEvent],
        tags=["geoadapt"],
    )
    def list_geoadapt_annotations(
        task: Annotated[TaskType | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> list[AnnotationEvent]:
        return geoadapt.list_annotations(task=task, limit=limit)

    @app.post(
        "/api/v1/geoadapt/adaptations",
        response_model=AdaptationRound,
        tags=["geoadapt"],
    )
    def create_geoadapt_adaptation(request: AdaptationRequest) -> AdaptationRound:
        try:
            return geoadapt.create_adaptation(request)
        except GeoAdaptValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/geoadapt/adaptations",
        response_model=list[AdaptationRound],
        tags=["geoadapt"],
    )
    def list_geoadapt_adaptations(
        task: Annotated[TaskType | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[AdaptationRound]:
        return geoadapt.list_adaptations(task=task, limit=limit)

    @app.get("/api/v1/research/claim-boundary", tags=["research"])
    def claim_boundary():  # type: ignore[no-untyped-def]
        return {
            "inference_view": [
                "runtime",
                "predicted area or candidate count",
                "model confidence proxy",
                "uncertainty proxy",
            ],
            "evaluation_view_requires_ground_truth": [
                "mIoU",
                "F1",
                "precision/recall",
                "mAP",
                "calibration error",
            ],
            "policy": "The UI never hard-codes benchmark accuracy as a property of a run.",
        }

    @app.get(
        "/api/v1/agent/conversations",
        response_model=list[AgentConversationSummary],
        tags=["agent"],
    )
    def list_agent_conversations(
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        include_archived: bool = False,
    ) -> list[AgentConversationSummary]:
        return conversations.list(limit=limit, include_archived=include_archived)

    @app.post(
        "/api/v1/agent/conversations",
        response_model=AgentConversation,
        tags=["agent"],
    )
    def create_agent_conversation(
        request: AgentConversationCreateRequest,
    ) -> AgentConversation:
        return conversations.create(request.title)

    @app.get(
        "/api/v1/agent/conversations/{conversation_id}",
        response_model=AgentConversation,
        tags=["agent"],
    )
    def get_agent_conversation(conversation_id: str) -> AgentConversation:
        try:
            return conversations.get(conversation_id)
        except ConversationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found") from exc

    @app.patch(
        "/api/v1/agent/conversations/{conversation_id}",
        response_model=AgentConversation,
        tags=["agent"],
    )
    def update_agent_conversation(
        conversation_id: str,
        request: AgentConversationUpdateRequest,
    ) -> AgentConversation:
        try:
            return conversations.update(
                conversation_id,
                title=request.title,
                archived=request.archived,
            )
        except ConversationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found") from exc

    @app.get("/api/v1/agent/status", response_model=AgentStatus, tags=["agent"])
    def agent_status() -> dict:
        return app.state.agent_bridge.status()

    @app.post(
        "/api/v1/agent/chat",
        response_model=AgentChatResponse,
        tags=["agent"],
    )
    def agent_chat(request: AgentChatRequest) -> dict:
        history: list[dict[str, str]] = []
        if request.conversation_id:
            try:
                conversation = conversations.get(request.conversation_id)
            except ConversationNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Conversation not found") from exc
            if conversation.archived:
                raise HTTPException(status_code=409, detail="Conversation is archived")
            history = conversations.prompt_history(request.conversation_id)
        try:
            result = app.state.agent_bridge.chat(
                request.message,
                allow_actions=request.allow_actions,
                current_job_id=request.current_job_id,
                history=history,
            )
        except GeoAgentIntegrationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        conversation_id = request.conversation_id
        if conversation_id is None:
            conversation_id = conversations.create().id
        conversations.append_exchange(
            conversation_id,
            user_content=request.message,
            assistant_content=result["answer"],
            executed_tools=result["executed_tools"],
            cancelled_tools=result["cancelled_tools"],
            allow_actions=request.allow_actions,
        )
        return {"conversation_id": conversation_id, **result}

    @app.get("/artifacts/jobs/{job_id}/outputs/{filename}", tags=["artifacts"])
    def download_artifact(job_id: str, filename: str) -> FileResponse:
        try:
            manifest = service.get_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found") from exc
        artifact = next(
            (item for item in manifest.artifacts if Path(item.url).name == filename),
            None,
        )
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        artifact_path = resolved_settings.artifact_root / "jobs" / job_id / "outputs" / filename
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(artifact_path, media_type=artifact.media_type)

    app.mount(
        "/static",
        StaticFiles(directory=resolved_settings.static_root),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(resolved_settings.static_root / "index.html")

    return app


async def _read_upload(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="Uploaded image exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)


app = create_app()
