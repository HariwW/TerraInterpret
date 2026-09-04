from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .catalog import DataCatalogService
from .evaluation import EvaluationService
from .models import (
    JobStatus,
    TaskType,
    WorkflowCreateRequest,
    WorkflowRecord,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from .registry import MODEL_BY_ID, MODEL_CARDS
from .service import JobService


class WorkflowNotFoundError(KeyError):
    pass


class WorkflowValidationError(ValueError):
    pass


class WorkflowService:
    """Persistent, auditable orchestration over datasets, jobs, and evaluations."""

    def __init__(
        self,
        root: Path,
        catalog: DataCatalogService,
        jobs: JobService,
        evaluation: EvaluationService,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog
        self.jobs = jobs
        self.evaluation = evaluation
        self._lock = threading.RLock()
        self._workflows: dict[str, WorkflowRecord] = {}
        self._load_existing()

    def create_plan(self, request: WorkflowCreateRequest) -> WorkflowRecord:
        dataset = self.catalog.get_dataset(request.dataset_id)
        if dataset.layout == "folder":
            raise WorkflowValidationError(
                "Folder datasets require batch orchestration, which is not available "
                "in this workflow"
            )
        if dataset.task_hint is not None and dataset.task_hint is not request.task:
            raise WorkflowValidationError(
                f"Dataset task hint is {dataset.task_hint.value}, not {request.task.value}"
            )
        roles = {asset.role for asset in dataset.assets}
        if request.task is TaskType.CHANGE_DETECTION and "secondary" not in roles:
            raise WorkflowValidationError("Change-detection workflow requires a paired dataset")
        model_ids = self._resolve_models(request.task, request.model_ids)
        model_parameters = self._resolve_model_parameters(
            model_ids,
            request.model_parameters,
            request.threshold,
        )
        workflow_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        steps = [WorkflowStep(id="validate-input", kind="validation", label="验证数据版本")]
        steps.extend(
            WorkflowStep(
                id=f"infer-{index + 1}",
                kind="inference",
                label=f"运行 {MODEL_BY_ID[model_id].name}",
                model_id=model_id,
            )
            for index, model_id in enumerate(model_ids)
        )
        if request.task in self.evaluation.SUPPORTED_TASKS:
            steps.append(
                WorkflowStep(
                    id="evaluate",
                    kind="evaluation",
                    label="绑定同一真值并执行可比评测",
                )
            )
        steps.append(WorkflowStep(id="summarize", kind="summary", label="汇总运行证据"))
        workflow = WorkflowRecord(
            id=workflow_id,
            name=" ".join(request.name.split())[:120],
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            task=request.task,
            model_ids=model_ids,
            model_parameters=model_parameters,
            status=WorkflowStatus.PLANNED,
            steps=steps,
            created_at=now,
            updated_at=now,
            summary={
                "planned_models": len(model_ids),
                "selection_policy": (
                    "explicit model list"
                    if request.model_ids
                    else "all ready registered models for task"
                ),
                "evaluation_policy": (
                    "shared ground truth required"
                    if request.task in self.evaluation.SUPPORTED_TASKS
                    else "no compatible metric suite registered"
                ),
            },
        )
        with self._lock:
            self._workflows[workflow.id] = workflow
            self._persist(workflow)
        return workflow.model_copy(deep=True)

    def queue(self, workflow_id: str) -> WorkflowRecord:
        workflow = self._mutable(workflow_id)
        if workflow.status is not WorkflowStatus.PLANNED:
            raise WorkflowValidationError("Only a planned workflow can be queued")
        workflow.status = WorkflowStatus.QUEUED
        workflow.updated_at = datetime.now(UTC)
        self._persist(workflow)
        return workflow.model_copy(deep=True)

    def execute(self, workflow_id: str) -> None:
        workflow = self._mutable(workflow_id)
        if workflow.status not in {WorkflowStatus.PLANNED, WorkflowStatus.QUEUED}:
            raise WorkflowValidationError("Workflow has already been executed")
        try:
            workflow.status = WorkflowStatus.RUNNING
            workflow.updated_at = datetime.now(UTC)
            self._persist(workflow)
            validation = self._step(workflow, "validate-input")
            self._start_step(workflow, validation)
            dataset = self.catalog.get_dataset(workflow.dataset_id)
            primary, primary_name, secondary, secondary_name = self.catalog.read_inputs(
                workflow.dataset_id
            )
            validation.status = WorkflowStepStatus.SUCCEEDED
            validation.completed_at = datetime.now(UTC)
            self._persist(workflow)

            successes = 0
            failures = 0
            for step in (item for item in workflow.steps if item.kind == "inference"):
                self._start_step(workflow, step)
                try:
                    manifest = self.jobs.create_job(
                        task=workflow.task,
                        model_id=step.model_id or "",
                        primary=primary,
                        primary_name=primary_name,
                        secondary=secondary,
                        secondary_name=secondary_name,
                        threshold=workflow.model_parameters.get(
                            step.model_id or "", {}
                        ).get("threshold"),
                        source=(f"workflow:{workflow.id}:dataset:{dataset.id}@{dataset.version}"),
                    )
                    step.job_id = manifest.id
                    workflow.job_ids.append(manifest.id)
                    self._persist(workflow)
                    self.jobs.run_job(manifest.id)
                    completed = self.jobs.get_job(manifest.id)
                    if completed.status is JobStatus.SUCCEEDED:
                        step.status = WorkflowStepStatus.SUCCEEDED
                        successes += 1
                    else:
                        step.status = WorkflowStepStatus.FAILED
                        step.error = completed.error or "Inference failed"
                        failures += 1
                except Exception as exc:
                    step.status = WorkflowStepStatus.FAILED
                    step.error = str(exc)[:500]
                    failures += 1
                step.completed_at = datetime.now(UTC)
                workflow.updated_at = step.completed_at
                self._persist(workflow)

            summary = self._step(workflow, "summarize")
            self._start_step(workflow, summary)
            workflow.summary.update(
                {
                    "successful_runs": successes,
                    "failed_runs": failures,
                    "job_ids": list(workflow.job_ids),
                }
            )
            summary.status = WorkflowStepStatus.SUCCEEDED
            summary.completed_at = datetime.now(UTC)
            if not successes:
                workflow.status = WorkflowStatus.FAILED
                workflow.error = "All inference steps failed"
            elif workflow.task in self.evaluation.SUPPORTED_TASKS:
                evaluation_step = self._step(workflow, "evaluate")
                evaluation_step.status = WorkflowStepStatus.BLOCKED
                evaluation_step.error = "等待用户上传同尺寸真值掩膜"
                workflow.status = WorkflowStatus.AWAITING_GROUND_TRUTH
            elif failures:
                workflow.status = WorkflowStatus.PARTIALLY_SUCCEEDED
            else:
                workflow.status = WorkflowStatus.SUCCEEDED
            workflow.updated_at = datetime.now(UTC)
            self._persist(workflow)
        except Exception as exc:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(exc)[:500]
            workflow.updated_at = datetime.now(UTC)
            self._persist(workflow)

    def evaluate(
        self,
        workflow_id: str,
        *,
        ground_truth: bytes,
        ground_truth_name: str,
        positive_threshold: int = 127,
    ) -> WorkflowRecord:
        workflow = self._mutable(workflow_id)
        if workflow.status is not WorkflowStatus.AWAITING_GROUND_TRUTH:
            raise WorkflowValidationError("Workflow is not waiting for ground-truth evaluation")
        step = self._step(workflow, "evaluate")
        self._start_step(workflow, step)
        step.error = None
        reports = []
        errors: list[str] = []
        for job_id in workflow.job_ids:
            job = self.jobs.get_job(job_id)
            if job.status is not JobStatus.SUCCEEDED:
                continue
            try:
                report = self.evaluation.create(
                    job_id=job.id,
                    ground_truth=ground_truth,
                    ground_truth_name=ground_truth_name,
                    positive_threshold=positive_threshold,
                )
                workflow.evaluation_ids.append(report.id)
                reports.append(report)
            except Exception as exc:
                errors.append(f"{job.model_id}: {exc}")
        if not reports:
            step.status = WorkflowStepStatus.FAILED
            step.error = "; ".join(errors)[:500] or "No succeeded run to evaluate"
            workflow.status = WorkflowStatus.FAILED
            workflow.error = step.error
        else:
            step.status = WorkflowStepStatus.SUCCEEDED if not errors else WorkflowStepStatus.FAILED
            step.evaluation_id = reports[0].id if len(reports) == 1 else None
            step.error = "; ".join(errors)[:500] if errors else None
            workflow.summary["evaluation_ids"] = list(workflow.evaluation_ids)
            workflow.summary["ranking"] = self._ranking(reports)
            inference_failures = any(
                item.status is WorkflowStepStatus.FAILED
                for item in workflow.steps
                if item.kind == "inference"
            )
            workflow.status = (
                WorkflowStatus.PARTIALLY_SUCCEEDED
                if errors or inference_failures
                else WorkflowStatus.SUCCEEDED
            )
        step.completed_at = datetime.now(UTC)
        workflow.updated_at = step.completed_at
        self._persist(workflow)
        return workflow.model_copy(deep=True)

    def get(self, workflow_id: str) -> WorkflowRecord:
        return self._mutable(workflow_id).model_copy(deep=True)

    def list(self, limit: int = 100) -> list[WorkflowRecord]:
        with self._lock:
            records = sorted(
                self._workflows.values(),
                key=lambda item: item.created_at,
                reverse=True,
            )[:limit]
            return [item.model_copy(deep=True) for item in records]

    def _resolve_models(self, task: TaskType, requested: list[str]) -> list[str]:
        candidates = list(dict.fromkeys(requested))
        if len(candidates) != len(requested):
            raise WorkflowValidationError("Workflow model IDs must be unique")
        if not candidates:
            candidates = [
                card.id
                for card in MODEL_CARDS
                if card.task is task and self.jobs.engine.status(card).ready
            ]
            candidates.sort(key=lambda model_id: MODEL_BY_ID[model_id].backend == "lite")
        if not candidates:
            raise WorkflowValidationError(f"No ready model supports {task.value}")
        for model_id in candidates:
            card = MODEL_BY_ID.get(model_id)
            if card is None:
                raise WorkflowValidationError(f"Unknown model: {model_id}")
            if card.task is not task:
                raise WorkflowValidationError(f"Model {model_id} does not support {task.value}")
            status = self.jobs.engine.status(card)
            if not status.ready:
                raise WorkflowValidationError(
                    f"Model {model_id} is unavailable: {status.reason or 'runtime not ready'}"
                )
        return candidates

    @staticmethod
    def _resolve_model_parameters(
        model_ids: list[str],
        supplied: dict[str, dict[str, float]],
        legacy_threshold: float | None,
    ) -> dict[str, dict[str, float]]:
        unknown_models = sorted(set(supplied) - set(model_ids))
        if unknown_models:
            raise WorkflowValidationError(
                f"Parameters supplied for unselected models: {', '.join(unknown_models)}"
            )
        resolved: dict[str, dict[str, float]] = {}
        for model_id in model_ids:
            card = MODEL_BY_ID[model_id]
            specs = {item.key: item for item in card.inference_parameters}
            values = supplied.get(model_id, {})
            unknown_keys = sorted(set(values) - set(specs))
            if unknown_keys:
                raise WorkflowValidationError(
                    f"Unsupported parameters for {model_id}: {', '.join(unknown_keys)}"
                )
            model_values: dict[str, float] = {}
            for key, spec in specs.items():
                value = values.get(
                    key,
                    legacy_threshold if legacy_threshold is not None else spec.default,
                )
                if not spec.minimum <= value <= spec.maximum:
                    raise WorkflowValidationError(
                        f"{model_id}.{key} must be between {spec.minimum} and {spec.maximum}"
                    )
                model_values[key] = round(float(value), 3)
            if model_values:
                resolved[model_id] = model_values
        return resolved

    def _mutable(self, workflow_id: str) -> WorkflowRecord:
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(workflow_id)
            return workflow

    @staticmethod
    def _step(workflow: WorkflowRecord, step_id: str) -> WorkflowStep:
        return next(item for item in workflow.steps if item.id == step_id)

    def _start_step(self, workflow: WorkflowRecord, step: WorkflowStep) -> None:
        step.status = WorkflowStepStatus.RUNNING
        step.started_at = datetime.now(UTC)
        step.error = None
        workflow.updated_at = step.started_at
        self._persist(workflow)

    @staticmethod
    def _ranking(reports: list) -> list[dict[str, object]]:
        ranked = sorted(
            reports,
            key=lambda item: (
                item.metrics.get("f1") is not None,
                item.metrics.get("f1") or -1.0,
            ),
            reverse=True,
        )
        return [
            {
                "rank": index + 1,
                "model_id": report.model_id,
                "evaluation_id": report.id,
                "f1": report.metrics.get("f1"),
                "iou": report.metrics.get("iou"),
            }
            for index, report in enumerate(ranked)
        ]

    def _persist(self, workflow: WorkflowRecord) -> None:
        workflow_dir = self.root / workflow.id
        workflow_dir.mkdir(parents=True, exist_ok=True)
        target = workflow_dir / "workflow.json"
        temporary = workflow_dir / ".workflow.tmp"
        temporary.write_text(
            json.dumps(workflow.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _load_existing(self) -> None:
        for path in self.root.glob("*/workflow.json"):
            try:
                workflow = WorkflowRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self._workflows[workflow.id] = workflow
