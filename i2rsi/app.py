from __future__ import annotations

import io
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .geoadapt import GeoAdaptNotFoundError, GeoAdaptService, GeoAdaptValidationError
from .models import (
    AdaptationRequest,
    AdaptationRound,
    AnnotationEvent,
    AnnotationRequest,
    DemoScenario,
    GeoAdaptState,
    HealthResponse,
    JobManifest,
    ReviewCandidate,
    ReviewStatus,
    TaskType,
)
from .registry import DEMO_ASSETS, DEMO_SCENARIOS, MODEL_CARDS
from .service import JobNotFoundError, JobService
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
    geoadapt = GeoAdaptService(resolved_settings.artifact_root / "geoadapt")
    service = JobService(resolved_settings, geoadapt=geoadapt)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        resolved_settings.artifact_root.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(
        title="I2RSI GeoAI Workbench API",
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
    app.state.geoadapt = geoadapt

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
    def models():  # type: ignore[no-untyped-def]
        return {"items": MODEL_CARDS, "count": len(MODEL_CARDS)}

    @app.get("/api/v1/scenarios", response_model=list[DemoScenario], tags=["demo"])
    def scenarios() -> list[DemoScenario]:
        return DEMO_SCENARIOS

    @app.get("/api/v1/demo-assets/{asset_id}", tags=["demo"])
    def demo_asset(asset_id: str) -> Response:
        asset = DEMO_ASSETS.get(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Demo asset not found")
        archive_path, media_type = asset
        if not resolved_settings.demo_archive.exists():
            raise HTTPException(status_code=404, detail="Demo archive is unavailable")
        try:
            with zipfile.ZipFile(resolved_settings.demo_archive) as archive:
                payload = archive.read(archive_path)
        except (KeyError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=500, detail="Demo archive is invalid") from exc
        return Response(
            io.BytesIO(payload).getvalue(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.post("/api/v1/demo-runs/{scenario_id}", response_model=JobManifest, tags=["demo"])
    def create_demo_run(
        scenario_id: str,
        background_tasks: BackgroundTasks,
        threshold: Annotated[float, Query(ge=0.05, le=0.95)] = 0.62,
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
        threshold: Annotated[float, Form(ge=0.05, le=0.95)] = 0.62,
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
    def list_jobs(limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[JobManifest]:
        return service.list_jobs(limit)

    @app.get("/api/v1/jobs/{job_id}", response_model=JobManifest, tags=["jobs"])
    def get_job(job_id: str) -> JobManifest:
        try:
            return service.get_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

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
    def annotate_geoadapt_review(
        candidate_id: str, request: AnnotationRequest
    ) -> AnnotationEvent:
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
