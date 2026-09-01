from __future__ import annotations

import json
import threading
import uuid
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from . import __version__
from .engine import DemoInterpretationEngine, sha256_file
from .geoadapt import GeoAdaptService
from .models import Artifact, JobManifest, JobStatus, TaskType
from .registry import DEMO_ASSETS, MODEL_BY_ID, SCENARIO_BY_ID
from .settings import Settings


class JobNotFoundError(KeyError):
    pass


class JobService:
    def __init__(
        self, settings: Settings, geoadapt: GeoAdaptService | None = None
    ) -> None:
        self.settings = settings
        self.jobs_root = settings.artifact_root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.engine = DemoInterpretationEngine(max_image_edge=settings.max_image_edge)
        self.geoadapt = geoadapt
        self._lock = threading.RLock()
        self._jobs: dict[str, JobManifest] = {}
        self._load_existing_jobs()

    def create_job(
        self,
        *,
        task: TaskType,
        model_id: str,
        primary: bytes,
        primary_name: str,
        secondary: bytes | None = None,
        secondary_name: str | None = None,
        threshold: float = 0.62,
        source: str = "upload",
    ) -> JobManifest:
        card = MODEL_BY_ID.get(model_id)
        if card is None:
            raise ValueError(f"Unknown model: {model_id}")
        if card.task is not task:
            raise ValueError(f"Model {model_id} does not support task {task.value}")
        if task is TaskType.CHANGE_DETECTION and not secondary:
            raise ValueError("Change detection requires two images")
        primary_meta = self._validate_payload(primary)
        secondary_meta: dict[str, int | str] | None = None
        if secondary is not None:
            secondary_meta = self._validate_payload(secondary)
            if (
                primary_meta["width_px"],
                primary_meta["height_px"],
            ) != (
                secondary_meta["width_px"],
                secondary_meta["height_px"],
            ):
                raise ValueError("Paired images must have identical pixel dimensions")

        job_id = uuid.uuid4().hex
        job_dir = self.jobs_root / job_id
        input_dir = job_dir / "inputs"
        input_dir.mkdir(parents=True, exist_ok=False)
        primary_path = input_dir / "primary.image"
        primary_path.write_bytes(primary)
        inputs = [
            self._input_record(
                primary_path, primary_name, "primary", source, primary_meta
            )
        ]
        if secondary is not None:
            secondary_path = input_dir / "secondary.image"
            secondary_path.write_bytes(secondary)
            inputs.append(
                self._input_record(
                    secondary_path,
                    secondary_name or "secondary.image",
                    "secondary",
                    source,
                    secondary_meta or {},
                )
            )

        manifest = JobManifest.queued(
            job_id=job_id,
            task=task,
            model_id=model_id,
            parameters={"threshold": round(float(threshold), 3)},
            inputs=inputs,
        )
        with self._lock:
            self._jobs[job_id] = manifest
            self._persist(manifest)
        return manifest.model_copy(deep=True)

    def create_demo_job(self, scenario_id: str, threshold: float = 0.62) -> JobManifest:
        scenario = SCENARIO_BY_ID.get(scenario_id)
        if scenario is None:
            raise ValueError(f"Unknown demo scenario: {scenario_id}")
        primary, primary_name = self._read_demo_asset(scenario.primary_asset)
        secondary: bytes | None = None
        secondary_name: str | None = None
        if scenario.secondary_asset:
            secondary, secondary_name = self._read_demo_asset(scenario.secondary_asset)
        return self.create_job(
            task=scenario.task,
            model_id=scenario.model_id,
            primary=primary,
            primary_name=primary_name,
            secondary=secondary,
            secondary_name=secondary_name,
            threshold=threshold,
            source=f"bundled-demo:{scenario_id}",
        )

    def run_job(self, job_id: str) -> None:
        try:
            manifest = self._get_mutable(job_id)
            manifest.status = JobStatus.RUNNING
            manifest.updated_at = datetime.now(UTC)
            self._persist(manifest)
            job_dir = self.jobs_root / job_id
            primary_path = job_dir / "inputs" / "primary.image"
            secondary_path = job_dir / "inputs" / "secondary.image"
            output = self.engine.run(
                task=manifest.task,
                primary_path=primary_path,
                secondary_path=secondary_path if secondary_path.exists() else None,
                output_dir=job_dir / "outputs",
                threshold=float(manifest.parameters["threshold"]),
            )
            artifacts = []
            for kind, (path, label, media_type) in output.files.items():
                artifacts.append(
                    Artifact(
                        kind=kind,
                        label=label,
                        url=f"/artifacts/jobs/{job_id}/outputs/{path.name}",
                        media_type=media_type,
                        sha256=sha256_file(path),
                    )
                )
            manifest.artifacts = artifacts
            manifest.metrics = output.metrics
            manifest.histogram = output.histogram
            manifest.legend = output.legend
            manifest.summary = output.summary
            manifest.provenance = {
                "app_version": __version__,
                "engine": self.engine.id,
                "engine_version": self.engine.version,
                "model_id": manifest.model_id,
                "task": manifest.task.value,
                "parameters": manifest.parameters,
                "input_sha256": [item["sha256"] for item in manifest.inputs],
                "coordinate_reference": "pixel coordinates; source images have no CRS metadata",
                "random_seed": None,
                "reproducibility": "deterministic CPU baseline",
                "claim_boundary": (
                    "Descriptive run statistics only. Accuracy metrics require "
                    "labelled ground truth."
                ),
            }
            manifest.status = JobStatus.SUCCEEDED
            manifest.updated_at = datetime.now(UTC)
            if self.geoadapt is not None:
                try:
                    candidates = self.geoadapt.ingest_job(manifest, output.features)
                    manifest.provenance["geoadapt"] = {
                        "status": "queued_for_review",
                        "review_candidate_count": len(candidates),
                        "acquisition": "uncertainty-diversity-v1",
                    }
                except ValueError as exc:
                    manifest.provenance["geoadapt"] = {
                        "status": "unavailable",
                        "reason": str(exc)[:200],
                    }
            self._persist(manifest)
        except Exception as exc:
            with self._lock:
                manifest = self._jobs.get(job_id)
                if manifest is not None:
                    manifest.status = JobStatus.FAILED
                    manifest.error = str(exc)[:500]
                    manifest.updated_at = datetime.now(UTC)
                    self._persist(manifest)

    def get_job(self, job_id: str) -> JobManifest:
        with self._lock:
            manifest = self._jobs.get(job_id)
            if manifest is None:
                raise JobNotFoundError(job_id)
            return manifest.model_copy(deep=True)

    def list_jobs(self, limit: int = 20) -> list[JobManifest]:
        with self._lock:
            manifests = sorted(
                self._jobs.values(), key=lambda item: item.created_at, reverse=True
            )[:limit]
            return [item.model_copy(deep=True) for item in manifests]

    def _get_mutable(self, job_id: str) -> JobManifest:
        with self._lock:
            manifest = self._jobs.get(job_id)
            if manifest is None:
                raise JobNotFoundError(job_id)
            return manifest

    def _validate_payload(self, payload: bytes) -> dict[str, int | str]:
        if not payload:
            raise ValueError("Uploaded image is empty")
        if len(payload) > self.settings.max_upload_bytes:
            limit_mb = self.settings.max_upload_bytes // (1024 * 1024)
            raise ValueError(f"Uploaded image exceeds {limit_mb} MB")
        try:
            with Image.open(BytesIO(payload)) as image:
                image_format = image.format
                width, height = image.size
                if image_format not in {"PNG", "JPEG"}:
                    raise ValueError("Only PNG and JPEG images are accepted")
                if width <= 0 or height <= 0:
                    raise ValueError("Image dimensions must be positive")
                if width * height > self.settings.max_image_pixels:
                    raise ValueError("Decoded image exceeds the configured pixel limit")
                image.verify()
        except ValueError:
            raise
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError("Uploaded file is not a valid PNG or JPEG image") from exc
        return {"format": image_format, "width_px": width, "height_px": height}

    @staticmethod
    def _input_record(
        path: Path,
        name: str,
        role: str,
        source: str,
        image_meta: dict[str, int | str],
    ) -> dict[str, Any]:
        safe_name = Path(name).name[:160] or f"{role}.image"
        return {
            "role": role,
            "name": safe_name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "source": source,
            **image_meta,
        }

    def _read_demo_asset(self, asset_id: str) -> tuple[bytes, str]:
        try:
            archive_path, _ = DEMO_ASSETS[asset_id]
        except KeyError as exc:
            raise ValueError(f"Unknown demo asset: {asset_id}") from exc
        if not self.settings.demo_archive.exists():
            raise ValueError("Bundled demo archive is unavailable")
        with zipfile.ZipFile(self.settings.demo_archive) as archive:
            info = archive.getinfo(archive_path)
            if info.file_size > self.settings.max_upload_bytes:
                raise ValueError("Bundled demo asset exceeds configured upload limit")
            return archive.read(info), Path(archive_path).name

    def _persist(self, manifest: JobManifest) -> None:
        job_dir = self.jobs_root / manifest.id
        job_dir.mkdir(parents=True, exist_ok=True)
        target = job_dir / "manifest.json"
        temporary = job_dir / ".manifest.tmp"
        temporary.write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _load_existing_jobs(self) -> None:
        manifests = sorted(
            self.jobs_root.glob("*/manifest.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[: self.settings.job_retention]
        for path in manifests:
            try:
                manifest = JobManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if manifest.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                manifest.status = JobStatus.FAILED
                manifest.error = "The previous process stopped before this job completed."
                manifest.updated_at = datetime.now(UTC)
                self._persist(manifest)
            self._jobs[manifest.id] = manifest
