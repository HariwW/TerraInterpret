from __future__ import annotations

import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from i2rsi.agent_bridge import GeoAgentBridge, GeoAgentIntegrationError


def _plain_geo_tool(**metadata: Any):  # type: ignore[no-untyped-def]
    def decorate(function):  # type: ignore[no-untyped-def]
        function.geo_metadata = metadata
        return function

    return decorate


def test_bridge_exposes_only_scoped_terrainterpret_tools(app: FastAPI) -> None:
    bridge: GeoAgentBridge = app.state.agent_bridge
    tools = bridge._build_tools(_plain_geo_tool)
    by_name = {tool.__name__: tool for tool in tools}

    assert set(by_name) == {
        "list_interpretation_capabilities",
        "list_recent_interpretation_runs",
        "inspect_interpretation_run",
        "list_registered_datasets",
        "inspect_registered_dataset",
        "inspect_model_card",
        "search_interpretation_runs",
        "list_evaluation_reports",
        "inspect_evaluation_report",
        "compare_evaluation_reports",
        "inspect_geoadapt_loop",
        "list_pending_review_candidates",
        "list_interpretation_workflows",
        "inspect_interpretation_workflow",
        "run_dataset_workflow",
        "run_demo_interpretation",
    }
    assert by_name["run_demo_interpretation"].geo_metadata["requires_confirmation"] is True
    assert by_name["run_demo_interpretation"].geo_metadata["long_running"] is True
    assert by_name["run_dataset_workflow"].geo_metadata["requires_confirmation"] is True
    assert by_name["run_dataset_workflow"].geo_metadata["long_running"] is True
    assert "run_python" not in by_name
    assert "delete" not in " ".join(by_name)

    capabilities = by_name["list_interpretation_capabilities"]()
    assert len(capabilities["models"]) == 14
    assert len(capabilities["scenarios"]) == 4
    assert "ground truth" in capabilities["claim_boundary"]


def test_bridge_queries_catalog_models_filtered_runs_and_evaluations(
    app: FastAPI,
) -> None:
    bridge: GeoAgentBridge = app.state.agent_bridge
    tools = {tool.__name__: tool for tool in bridge._build_tools(_plain_geo_tool)}

    queued = bridge.service.create_demo_job("road-network")
    bridge.service.run_job(queued.id)
    job = bridge.service.get_job(queued.id)
    input_path = bridge.service.jobs_root / job.id / "inputs" / "primary.image"
    dataset = bridge.catalog.create_dataset(
        name="Road audit scene",
        description="Synthetic test scene",
        task_hint=job.task,
        primary=input_path.read_bytes(),
        primary_name="road.png",
    )
    mask_path = bridge.service.jobs_root / job.id / "outputs" / "mask.png"
    first_report = bridge.evaluation.create(
        job_id=job.id,
        ground_truth=mask_path.read_bytes(),
        ground_truth_name="truth.png",
    )
    second_report = bridge.evaluation.create(
        job_id=job.id,
        ground_truth=mask_path.read_bytes(),
        ground_truth_name="truth-copy.png",
    )

    datasets = tools["list_registered_datasets"](task="road_extraction")
    assert [item["id"] for item in datasets] == [dataset.id]
    assert datasets[0]["layout"] == "single"
    assert datasets[0]["sample_count"] == 1
    inspected_dataset = tools["inspect_registered_dataset"](dataset.id)
    assert inspected_dataset["assets"][0]["sha256"] == dataset.assets[0].sha256

    model = tools["inspect_model_card"]("roadgraph-lite-v2")
    assert model["task"] == "road_extraction"
    runs = tools["search_interpretation_runs"](
        status="succeeded",
        task="road_extraction",
        model_id="roadgraph-lite-v2",
    )
    assert [item["id"] for item in runs] == [job.id]

    reports = tools["list_evaluation_reports"](task="road_extraction")
    assert {item["id"] for item in reports} == {first_report.id, second_report.id}
    inspected_report = tools["inspect_evaluation_report"](first_report.id)
    assert inspected_report["ground_truth_sha256"] == first_report.ground_truth_sha256
    comparison = tools["compare_evaluation_reports"](f"{first_report.id},{second_report.id}")
    assert comparison["comparable"] is True
    assert comparison["best_by_metric"]["iou"]["value"] == 1.0
    assert "direct metric comparison is permitted" in comparison["interpretation"]

    with pytest.raises(ValueError, match="Unknown task"):
        tools["search_interpretation_runs"](task="not-a-task")
    with pytest.raises(ValueError, match="between 2 and 8"):
        tools["compare_evaluation_reports"](first_report.id)


def test_bridge_maps_geoagent_response_and_gates_action_tools(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    fake_module = ModuleType("geoagent")

    class FakeContext:
        def __init__(self, *, metadata: dict[str, str]) -> None:
            self.metadata = metadata

    def create_agent(**kwargs: Any) -> Any:
        captured.update(kwargs)

        class FakeAgent:
            def chat(self, message: str) -> Any:
                captured["message"] = message
                return SimpleNamespace(
                    success=True,
                    answer_text="最近运行可复现。",
                    executed_tools=["list_recent_interpretation_runs"],
                    cancelled_tools=[],
                )

        return FakeAgent()

    fake_module.GeoAgentContext = FakeContext
    fake_module.create_agent = create_agent
    fake_module.geo_tool = _plain_geo_tool
    monkeypatch.setitem(sys.modules, "geoagent", fake_module)

    bridge: GeoAgentBridge = app.state.agent_bridge
    monkeypatch.setattr(bridge, "_package_installed", lambda: True)
    result = bridge.chat(
        "总结最近运行",
        allow_actions=False,
        current_job_id="abc123",
        history=[
            {"role": "user", "content": "先检查道路工作流"},
            {"role": "assistant", "content": "已找到一个工作流"},
        ],
    )

    assert result["answer"] == "最近运行可复现。"
    assert result["executed_tools"] == ["list_recent_interpretation_runs"]
    assert captured["message"] == "总结最近运行"
    assert "abc123" in captured["context"].metadata["system_prompt"]
    assert "先检查道路工作流" in captured["context"].metadata["system_prompt"]
    assert captured["confirm"](SimpleNamespace(tool_name="run_demo_interpretation")) is False
    assert (
        captured["confirm"](SimpleNamespace(tool_name="list_recent_interpretation_runs")) is False
    )

    bridge.chat("运行城市变化示例", allow_actions=True)
    assert captured["confirm"](SimpleNamespace(tool_name="run_demo_interpretation")) is True
    assert captured["confirm"](SimpleNamespace(tool_name="delete_everything")) is False


def test_bridge_maps_deepseek_to_openai_compatible_config(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    fake_module = ModuleType("geoagent")

    class FakeConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeContext:
        def __init__(self, *, metadata: dict[str, str]) -> None:
            self.metadata = metadata

    def create_agent(**kwargs: Any) -> Any:
        captured.update(kwargs)

        class FakeAgent:
            def chat(self, message: str) -> Any:
                return SimpleNamespace(
                    success=True,
                    answer_text=message,
                    executed_tools=[],
                    cancelled_tools=[],
                )

        return FakeAgent()

    fake_module.GeoAgentConfig = FakeConfig
    fake_module.GeoAgentContext = FakeContext
    fake_module.create_agent = create_agent
    fake_module.geo_tool = _plain_geo_tool
    monkeypatch.setitem(sys.modules, "geoagent", fake_module)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    bridge: GeoAgentBridge = app.state.agent_bridge
    monkeypatch.setattr(bridge, "settings", replace(bridge.settings, agent_provider="deepseek"))
    monkeypatch.setattr(bridge, "_package_installed", lambda: True)

    result = bridge.chat("检查编排状态")
    config = captured["config"].kwargs

    assert result["answer"] == "检查编排状态"
    assert config["provider"] == "openai-compatible"
    assert config["model"] == "deepseek-v4-flash"
    assert config["openai_compatible_base_url"] == "https://api.deepseek.com"
    assert config["client_args"] == {"api_key": "test-key"}
    assert config["temperature"] == 0.0


def test_agent_chat_endpoint_returns_actionable_unavailable_error(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise GeoAgentIntegrationError("GeoAgent test runtime is unavailable")

    monkeypatch.setattr(app.state.agent_bridge, "chat", unavailable)
    response = client.post(
        "/api/v1/agent/chat",
        json={"message": "总结当前工作台"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "GeoAgent test runtime is unavailable"
