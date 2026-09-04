from __future__ import annotations

import importlib.util
import json
import os
from importlib import metadata
from typing import Any

from .catalog import DataCatalogService
from .evaluation import EvaluationService
from .geoadapt import GeoAdaptService
from .models import JobStatus, TaskType
from .registry import MODEL_BY_ID, MODEL_CARDS
from .service import JobService
from .settings import Settings
from .workflow import WorkflowService


class GeoAgentIntegrationError(RuntimeError):
    """Raised when the optional GeoAgent runtime cannot serve a request."""


class GeoAgentBridge:
    """Bind GeoAgent to TerraInterpret's existing service contracts.

    The bridge deliberately exposes a small, typed tool surface instead of
    allowing arbitrary Python or filesystem access. Read-only inspection is
    always available; starting a demo run requires per-request approval.
    """

    ACTION_TOOLS = frozenset({"run_demo_interpretation", "run_dataset_workflow"})

    def __init__(
        self,
        settings: Settings,
        service: JobService,
        geoadapt: GeoAdaptService,
        catalog: DataCatalogService,
        evaluation: EvaluationService,
        workflow: WorkflowService,
    ) -> None:
        self.settings = settings
        self.service = service
        self.geoadapt = geoadapt
        self.catalog = catalog
        self.evaluation = evaluation
        self.workflow = workflow

    def status(self) -> dict[str, Any]:
        installed = self._package_installed()
        version: str | None = None
        if installed:
            try:
                version = metadata.version("GeoAgent")
            except metadata.PackageNotFoundError:
                version = "development"
        enabled = self.settings.agent_enabled
        deepseek_selected = self.settings.agent_provider == "deepseek"
        deepseek_configured = bool(os.environ.get("DEEPSEEK_API_KEY"))
        ready = enabled and installed and (not deepseek_selected or deepseek_configured)
        return {
            "enabled": enabled,
            "installed": installed,
            "ready": ready,
            "package_version": version,
            "provider": self.settings.agent_provider or "auto",
            "model": (
                self.settings.agent_model or "deepseek-v4-flash"
                if deepseek_selected
                else self.settings.agent_model
            ),
            "safe_mode": (
                "read-only by default; demo and dataset workflow execution require "
                "explicit approval"
            ),
            "setup_hint": (
                "Set DEEPSEEK_API_KEY and restart TerraInterpret."
                if installed and deepseek_selected and not deepseek_configured
                else None
                if installed
                else 'Install with `pip install -e ".[agent-openai]"` or another provider extra.'
            ),
        }

    def chat(
        self,
        message: str,
        *,
        allow_actions: bool = False,
        current_job_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.agent_enabled:
            raise GeoAgentIntegrationError(
                "GeoAgent integration is disabled. Set I2RSI_AGENT_ENABLED=1."
            )
        if not self._package_installed():
            raise GeoAgentIntegrationError(
                'GeoAgent is not installed. Run `pip install -e ".[agent-openai]"` '
                "or install the extra for your selected provider."
            )

        try:
            from geoagent import GeoAgentContext, create_agent, geo_tool
        except ImportError as exc:
            raise GeoAgentIntegrationError(
                "GeoAgent could not be imported. Reinstall the selected agent extra."
            ) from exc

        tools = self._build_tools(geo_tool)
        context_note = (
            "You are the TerraInterpret copilot. Use tools to inspect registered datasets, "
            "model cards, workflows, filtered runs, evaluations, and the live review loop. "
            "Never present confidence, uncertainty, saliency, coverage, or predicted area "
            "as benchmark accuracy. mIoU, F1, precision, recall, mAP, and calibration error "
            "require labelled ground truth and a recorded evaluation protocol. "
            "Do not claim that the transparent CPU baselines are trained GeoAI models. "
            "Folder-layout datasets are versioned collections; do not send them to "
            "single-scene tools or workflows."
        )
        if current_job_id:
            context_note += f" The workbench currently displays run {current_job_id}."
        if history:
            context_note += (
                "\n\nPersistent conversation memory follows. Use it to resolve references "
                "and maintain continuity, but keep current tool evidence authoritative.\n"
                f"<conversation-history-json>{json.dumps(history, ensure_ascii=False)}"
                "</conversation-history-json>"
            )
        context = GeoAgentContext(metadata={"system_prompt": context_note})

        def confirm(request: Any) -> bool:
            return bool(allow_actions and getattr(request, "tool_name", "") in self.ACTION_TOOLS)

        kwargs: dict[str, Any] = {
            "context": context,
            "tools": tools,
            "fast": True,
            "confirm": confirm,
        }
        if self.settings.agent_provider == "deepseek":
            from geoagent import GeoAgentConfig

            api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
            if not api_key:
                raise GeoAgentIntegrationError(
                    "DeepSeek is selected but DEEPSEEK_API_KEY is not configured."
                )
            kwargs["config"] = GeoAgentConfig(
                provider="openai-compatible",
                model=self.settings.agent_model or "deepseek-v4-flash",
                openai_compatible_base_url=os.environ.get(
                    "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                ),
                client_args={"api_key": api_key},
                temperature=0.0,
            )
        elif self.settings.agent_provider:
            kwargs["provider"] = self.settings.agent_provider
        if self.settings.agent_model and self.settings.agent_provider != "deepseek":
            kwargs["model_id"] = self.settings.agent_model

        try:
            agent = create_agent(**kwargs)
            result = agent.chat(message)
        except Exception as exc:
            raise GeoAgentIntegrationError(self._friendly_error(exc)) from exc

        if not result.success:
            raise GeoAgentIntegrationError(
                result.error_message or "GeoAgent could not complete the request."
            )
        return {
            "answer": result.answer_text or "",
            "executed_tools": list(result.executed_tools),
            "cancelled_tools": list(result.cancelled_tools),
            "action_mode": allow_actions,
        }

    def _build_tools(self, geo_tool: Any) -> list[Any]:
        service = self.service
        geoadapt = self.geoadapt
        catalog = self.catalog
        evaluation = self.evaluation
        workflow = self.workflow

        @geo_tool(category="terra", available_in=("full", "fast"))
        def list_interpretation_capabilities() -> dict[str, Any]:
            """List TerraInterpret tasks, registered models, and bundled scenarios."""
            return {
                "tasks": [card.task.value for card in MODEL_CARDS],
                "models": [
                    {
                        "id": card.id,
                        "name": card.name,
                        "task": card.task.value,
                        "stage": card.stage,
                        "limitations": card.limitations,
                        "runtime_status": service.engine.status(card).model_dump(mode="json"),
                    }
                    for card in MODEL_CARDS
                ],
                "scenarios": [
                    scenario.model_dump(mode="json")
                    for scenario in service.resolved_demo_scenarios()
                ],
                "claim_boundary": (
                    "Current runs expose descriptive proxy statistics only; accuracy metrics "
                    "require labelled ground truth and a versioned evaluation protocol."
                ),
            }

        @geo_tool(category="terra", available_in=("full", "fast"))
        def list_recent_interpretation_runs(limit: int = 5) -> list[dict[str, Any]]:
            """List recent TerraInterpret runs with status and concise observations."""
            bounded_limit = max(1, min(int(limit), 20))
            return [self._job_summary(job) for job in service.list_jobs(bounded_limit)]

        @geo_tool(category="terra", available_in=("full", "fast"))
        def inspect_interpretation_run(run_id: str) -> dict[str, Any]:
            """Inspect one run, including provenance, artifacts, and proxy statistics."""
            return self._job_summary(service.get_job(run_id), detailed=True)

        @geo_tool(category="terra-data", available_in=("full", "fast"))
        def list_registered_datasets(
            limit: int = 10,
            task: str = "",
        ) -> list[dict[str, Any]]:
            """List versioned datasets, optionally filtered by task name."""
            bounded_limit = max(1, min(int(limit), 50))
            task_filter = self._task_filter(task)
            records = catalog.list_datasets(limit=500)
            if task_filter is not None:
                records = [item for item in records if item.task_hint is task_filter]
            return [self._dataset_summary(item) for item in records[:bounded_limit]]

        @geo_tool(category="terra-data", available_in=("full", "fast"))
        def inspect_registered_dataset(dataset_id: str) -> dict[str, Any]:
            """Inspect one dataset version and its content-addressed image assets."""
            return self._dataset_summary(catalog.get_dataset(dataset_id), detailed=True)

        @geo_tool(category="terra-model", available_in=("full", "fast"))
        def inspect_model_card(model_id: str) -> dict[str, Any]:
            """Inspect a model card, including inputs, strengths, limits, and metric scope."""
            card = MODEL_BY_ID.get(model_id)
            if card is None:
                raise ValueError(f"Unknown model: {model_id}")
            return {
                **card.model_dump(mode="json"),
                "runtime_status": service.engine.status(card).model_dump(mode="json"),
            }

        @geo_tool(category="terra-run", available_in=("full", "fast"))
        def search_interpretation_runs(
            limit: int = 10,
            status: str = "",
            task: str = "",
            model_id: str = "",
        ) -> list[dict[str, Any]]:
            """Filter runs by status, task, and model ID."""
            bounded_limit = max(1, min(int(limit), 50))
            status_filter: JobStatus | None = None
            if status.strip():
                try:
                    status_filter = JobStatus(status.strip())
                except ValueError as exc:
                    raise ValueError(f"Unknown run status: {status}") from exc
            task_filter = self._task_filter(task)
            jobs = service.list_jobs(
                bounded_limit,
                status=status_filter,
                task=task_filter,
                model_id=model_id.strip() or None,
            )
            return [self._job_summary(job) for job in jobs]

        @geo_tool(category="terra-evaluation", available_in=("full", "fast"))
        def list_evaluation_reports(
            limit: int = 10,
            task: str = "",
        ) -> list[dict[str, Any]]:
            """List ground-truth evaluation reports, optionally filtered by task."""
            bounded_limit = max(1, min(int(limit), 50))
            task_filter = self._task_filter(task)
            reports = evaluation.list_reports(limit=500)
            if task_filter is not None:
                reports = [item for item in reports if item.task is task_filter]
            return [self._evaluation_summary(item) for item in reports[:bounded_limit]]

        @geo_tool(category="terra-evaluation", available_in=("full", "fast"))
        def inspect_evaluation_report(evaluation_id: str) -> dict[str, Any]:
            """Inspect metrics, confusion counts, hashes, and scope for one evaluation."""
            return self._evaluation_summary(evaluation.get_report(evaluation_id), detailed=True)

        @geo_tool(category="terra-evaluation", available_in=("full", "fast"))
        def compare_evaluation_reports(evaluation_ids: str) -> dict[str, Any]:
            """Compare 2-8 evaluation IDs supplied as a comma-separated string."""
            ids = [item.strip() for item in evaluation_ids.split(",") if item.strip()]
            if not 2 <= len(ids) <= 8:
                raise ValueError("Provide between 2 and 8 evaluation IDs")
            if len(set(ids)) != len(ids):
                raise ValueError("Evaluation IDs must be unique")
            reports = [evaluation.get_report(item) for item in ids]
            comparable = (
                len({item.task for item in reports}) == 1
                and len({item.metric_suite for item in reports}) == 1
                and len({item.ground_truth_sha256 for item in reports}) == 1
            )
            best_by_metric: dict[str, dict[str, Any]] = {}
            if comparable:
                for metric in reports[0].metrics:
                    candidates = [
                        (item.id, item.metrics.get(metric))
                        for item in reports
                        if item.metrics.get(metric) is not None
                    ]
                    if candidates:
                        best_id, best_value = max(candidates, key=lambda pair: pair[1])
                        best_by_metric[metric] = {
                            "evaluation_id": best_id,
                            "value": best_value,
                        }
            return {
                "comparable": comparable,
                "reports": [self._evaluation_summary(item) for item in reports],
                "best_by_metric": best_by_metric,
                "interpretation": (
                    "Reports share task, metric suite, and ground-truth hash; direct metric "
                    "comparison is permitted within their recorded scope."
                    if comparable
                    else "Side-by-side display only: task, metric suite, or ground truth differs. "
                    "Do not infer a model ranking from these reports."
                ),
            }

        @geo_tool(category="terra", available_in=("full", "fast"))
        def inspect_geoadapt_loop() -> dict[str, Any]:
            """Inspect the active-learning review and feedback-calibration state."""
            return geoadapt.state().model_dump(mode="json")

        @geo_tool(category="terra", available_in=("full", "fast"))
        def list_pending_review_candidates(limit: int = 5) -> list[dict[str, Any]]:
            """List the highest-priority pending candidates for human review."""
            bounded_limit = max(1, min(int(limit), 20))
            candidates = geoadapt.list_reviews(limit=bounded_limit)
            return [
                {
                    "id": item.id,
                    "run_id": item.job_id,
                    "task": item.task.value,
                    "suggested_label": item.suggested_label,
                    "uncertainty_score": item.uncertainty_score,
                    "diversity_score": item.diversity_score,
                    "acquisition_score": item.acquisition_score,
                    "status": item.status.value,
                }
                for item in candidates
            ]

        @geo_tool(category="terra-workflow", available_in=("full", "fast"))
        def list_interpretation_workflows(limit: int = 10) -> list[dict[str, Any]]:
            """List persisted multi-model workflows and their current state."""
            bounded_limit = max(1, min(int(limit), 50))
            return [item.model_dump(mode="json") for item in workflow.list(limit=bounded_limit)]

        @geo_tool(category="terra-workflow", available_in=("full", "fast"))
        def inspect_interpretation_workflow(workflow_id: str) -> dict[str, Any]:
            """Inspect one workflow plan, step states, runs, evaluations, and ranking."""
            return workflow.get(workflow_id).model_dump(mode="json")

        @geo_tool(
            category="terra-action",
            requires_confirmation=True,
            long_running=True,
            available_in=("full", "fast"),
        )
        def run_dataset_workflow(
            dataset_id: str,
            task: str,
            model_ids: str = "",
            model_thresholds: str = "",
            threshold: float | None = None,
            name: str = "GeoAgent 多模型解译",
        ) -> dict[str, Any]:
            """Plan and execute a registered dataset with one or more ready models.

            Supply model IDs as comma-separated values. Per-model thresholds use
            ``model-id=value`` pairs separated by commas. When omitted, model-card
            defaults are used. Binary workflows pause for user-supplied ground truth.
            """
            from .models import WorkflowCreateRequest

            selected = [item.strip() for item in model_ids.split(",") if item.strip()]
            per_model: dict[str, dict[str, float]] = {}
            for entry in (item.strip() for item in model_thresholds.split(",") if item.strip()):
                try:
                    model_id, value = entry.split("=", 1)
                    per_model[model_id.strip()] = {"threshold": float(value)}
                except ValueError as exc:
                    raise ValueError(
                        "model_thresholds must use comma-separated model-id=value pairs"
                    ) from exc
            task_value = self._task_filter(task)
            if task_value is None:
                raise ValueError("Workflow task is required")
            plan = workflow.create_plan(
                WorkflowCreateRequest(
                    name=name,
                    dataset_id=dataset_id,
                    task=task_value,
                    model_ids=selected,
                    model_parameters=per_model,
                    threshold=threshold,
                )
            )
            workflow.queue(plan.id)
            workflow.execute(plan.id)
            return workflow.get(plan.id).model_dump(mode="json")

        @geo_tool(
            category="terra-action",
            requires_confirmation=True,
            long_running=True,
            available_in=("full", "fast"),
        )
        def run_demo_interpretation(
            scenario_id: str,
            threshold: float | None = None,
        ) -> dict[str, Any]:
            """Run one registered demo scenario after explicit action approval."""
            manifest = service.create_demo_job(scenario_id, threshold)
            service.run_job(manifest.id)
            return self._job_summary(service.get_job(manifest.id), detailed=True)

        return [
            list_interpretation_capabilities,
            list_recent_interpretation_runs,
            inspect_interpretation_run,
            list_registered_datasets,
            inspect_registered_dataset,
            inspect_model_card,
            search_interpretation_runs,
            list_evaluation_reports,
            inspect_evaluation_report,
            compare_evaluation_reports,
            inspect_geoadapt_loop,
            list_pending_review_candidates,
            list_interpretation_workflows,
            inspect_interpretation_workflow,
            run_dataset_workflow,
            run_demo_interpretation,
        ]

    @staticmethod
    def _job_summary(job: Any, *, detailed: bool = False) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "id": job.id,
            "task": job.task.value,
            "model_id": job.model_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "summary": job.summary,
            "metrics": job.metrics,
        }
        if detailed:
            summary.update(
                {
                    "parameters": job.parameters,
                    "artifacts": [item.model_dump(mode="json") for item in job.artifacts],
                    "provenance": job.provenance,
                    "error": job.error,
                }
            )
        return summary

    @staticmethod
    def _dataset_summary(dataset: Any, *, detailed: bool = False) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "id": dataset.id,
            "version": dataset.version,
            "name": dataset.name,
            "task_hint": dataset.task_hint.value if dataset.task_hint else None,
            "layout": dataset.layout,
            "sample_count": dataset.sample_count,
            "asset_count": len(dataset.assets),
            "coordinate_space": dataset.coordinate_space,
            "created_at": dataset.created_at.isoformat(),
        }
        if detailed:
            summary.update(
                {
                    "description": dataset.description,
                    "source": dataset.source,
                    "assets": [item.model_dump(mode="json") for item in dataset.assets],
                }
            )
        return summary

    @staticmethod
    def _evaluation_summary(report: Any, *, detailed: bool = False) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "id": report.id,
            "run_id": report.job_id,
            "task": report.task.value,
            "model_id": report.model_id,
            "metric_suite": report.metric_suite,
            "metrics": report.metrics,
            "created_at": report.created_at.isoformat(),
        }
        if detailed:
            summary.update(
                {
                    "ground_truth_name": report.ground_truth_name,
                    "ground_truth_sha256": report.ground_truth_sha256,
                    "prediction_sha256": report.prediction_sha256,
                    "positive_threshold": report.positive_threshold,
                    "confusion": report.confusion,
                    "pixel_count": report.pixel_count,
                    "claim_scope": report.claim_scope,
                }
            )
        return summary

    @staticmethod
    def _task_filter(value: str) -> TaskType | None:
        if not value.strip():
            return None
        try:
            return TaskType(value.strip())
        except ValueError as exc:
            raise ValueError(f"Unknown task: {value}") from exc

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()
        if "access token" in lowered or "api key" in lowered:
            return (
                "The selected GeoAgent provider is not authenticated. Configure its API key "
                "or run the provider login command, then restart TerraInterpret."
            )
        return message

    @staticmethod
    def _package_installed() -> bool:
        try:
            return importlib.util.find_spec("geoagent") is not None
        except (ImportError, ValueError):
            return False
