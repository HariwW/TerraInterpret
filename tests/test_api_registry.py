from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


def test_health_reports_runtime_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "2.3.0"
    assert payload["engine"] == "hybrid-model-router"
    assert payload["demo_archive"] is True
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert "object-src 'none'" in response.headers["content-security-policy"]


def test_workbench_exposes_explicit_pending_state_and_scenario_result_cache(
) -> None:
    static_root = Path(__file__).parents[1] / "i2rsi" / "static"
    index = (static_root / "index.html").read_text(encoding="utf-8")
    script = (static_root / "app.js").read_text(encoding="utf-8")

    assert "当前场景尚未运行" in index
    assert "点击“运行示例”开始解译" in index
    assert "scenarioJobs: new Map()" in script
    assert "state.scenarioJobs.set(scenarioId, job)" in script
    assert "renderJob(completedJob, {notify: false})" in script
    assert "bootstrapScenarioExamples()" in script
    assert 'state.scenarioJobs.has(state.currentScenario?.id)' in script


def test_model_catalog_groups_cards_by_interpretation_task() -> None:
    static_root = Path(__file__).parents[1] / "i2rsi" / "static"
    script = (static_root / "app.js").read_text(encoding="utf-8")
    styles = (static_root / "app.css").read_text(encoding="utf-8")

    assert 'const taskOrder = ["change_detection", "land_cover", "object_detection"' in script
    assert 'group.className = "model-group"' in script
    assert 'grid.className = "model-group-grid"' in script
    assert "个模型 · ${readyCount} 个可运行" in script
    assert ".model-group-grid" in styles


def test_model_registry_exposes_baselines_and_pretrained_cards(client: TestClient) -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == len(payload["items"]) == 14
    baseline_ids = {
        "geochange-lite-v2",
        "geochange-robust-v3",
        "landcover-lite-v2",
        "geodetect-lite-v2",
        "roadgraph-lite-v2",
    }
    assert baseline_ids < {item["id"] for item in payload["items"]}
    assert {
        "changer-r18-levircd",
        "deeplabv3plus-r18-loveda",
        "deeplabv3plus-r50-loveda",
        "deeplabv3plus-r101-loveda",
        "deeplabv3plus-r18-loveda-road",
        "deeplabv3plus-r50-loveda-road",
        "yolo11n-obb-dota",
        "yolo26n-obb-dota",
        "yolo26s-obb-dota",
    } < {item["id"] for item in payload["items"]}
    assert {item["task"] for item in payload["items"]} == {
        "change_detection",
        "land_cover",
        "object_detection",
        "road_extraction",
    }
    for card in (item for item in payload["items"] if item["id"] in baseline_ids):
        assert card["reference_metrics"] == {}
        assert card["stage"] in {"demo baseline", "enhanced baseline"}
        assert card["limitations"]
        assert card["expected_inputs"]
        assert card["metric_scope"]
        assert card["runtime_status"]["ready"] is True

    pretrained = [item for item in payload["items"] if item["id"] not in baseline_ids]
    assert all(item["stage"] == "public pretrained" for item in pretrained)
    assert all(item["runtime_status"]["ready"] is False for item in pretrained)
    assert all(item["license"] for item in pretrained)
    cards = {item["id"]: item for item in payload["items"]}
    assert {item["id"] for item in payload["items"] if item["is_default"]} == {
        "geochange-robust-v3",
        "landcover-lite-v2",
        "geodetect-lite-v2",
        "roadgraph-lite-v2",
    }
    assert cards["landcover-lite-v2"]["inference_parameters"] == []
    assert cards["geodetect-lite-v2"]["inference_parameters"] == []
    assert cards["deeplabv3plus-r18-loveda"]["inference_parameters"][0]["label"] == (
        "最低像素置信度"
    )
    assert cards["yolo11n-obb-dota"]["inference_parameters"][0]["default"] == 0.25

    detail = client.get("/api/v1/models/geochange-lite-v2")
    assert detail.status_code == 200
    assert detail.json()["name"] == "GeoChange Lite"
    assert client.get("/api/v1/models/not-registered").status_code == 404


def test_scenario_registry_matches_models_and_assets(client: TestClient) -> None:
    models = {item["id"]: item for item in client.get("/api/v1/models").json()["items"]}

    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert {scenario["id"] for scenario in scenarios} == {
        "urban-change",
        "land-cover-mapping",
        "aircraft-proposals",
        "road-network",
    }
    for scenario in scenarios:
        assert scenario["model_id"] in models
        assert models[scenario["model_id"]]["task"] == scenario["task"]
        assert scenario["primary_asset"]
    change = next(item for item in scenarios if item["id"] == "urban-change")
    assert change["secondary_asset"] == "cd-after"


def test_demo_asset_is_served_from_archive(
    client: TestClient, sample_images: dict[str, bytes]
) -> None:
    response = client.get("/api/v1/demo-assets/cd-before")

    assert response.status_code == 200
    assert response.content == sample_images["before"]
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert client.get("/api/v1/demo-assets/not-registered").status_code == 404


def test_claim_boundary_separates_inference_from_evaluation(client: TestClient) -> None:
    response = client.get("/api/v1/research/claim-boundary")

    assert response.status_code == 200
    payload = response.json()
    evaluation_metrics = " ".join(payload["evaluation_view_requires_ground_truth"]).lower()
    assert "miou" in evaluation_metrics
    assert "f1" in evaluation_metrics
    assert "map" in evaluation_metrics
    assert "ground truth" in payload["policy"].lower() or "accuracy" in payload["policy"].lower()


def test_unknown_job_and_invalid_demo_request_are_explicit(client: TestClient) -> None:
    missing_job = client.get("/api/v1/jobs/does-not-exist")
    missing_scenario = client.post("/api/v1/demo-runs/does-not-exist")
    invalid_threshold = client.post("/api/v1/demo-runs/urban-change?threshold=1.0")

    assert missing_job.status_code == 404
    assert missing_job.json()["detail"] == "Job not found"
    assert missing_scenario.status_code == 400
    assert "Unknown demo scenario" in missing_scenario.json()["detail"]
    assert invalid_threshold.status_code == 422


def test_unavailable_pretrained_model_never_falls_back_to_lite(
    client: TestClient, sample_images: dict[str, bytes]
) -> None:
    response = client.post(
        "/api/v1/jobs",
        data={
            "task": "object_detection",
            "model_id": "yolo11n-obb-dota",
            "threshold": "0.25",
        },
        files={"primary": ("objects.jpg", sample_images["objects"], "image/jpeg")},
    )

    assert response.status_code == 400
    assert "unavailable" in response.json()["detail"]
    assert "models-setup" in response.json()["detail"]


def test_agent_status_is_available_without_forcing_optional_runtime(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/agent/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["provider"] == "auto"
    assert payload["ready"] is (payload["enabled"] and payload["installed"])
    assert "read-only" in payload["safe_mode"]
