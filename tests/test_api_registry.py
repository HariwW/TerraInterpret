from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient


def test_health_reports_runtime_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "2.1.0"
    assert payload["engine"] == "transparent-cpu-baselines"
    assert payload["demo_archive"] is True
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert "object-src 'none'" in response.headers["content-security-policy"]


def test_model_registry_exposes_honest_baseline_cards(client: TestClient) -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == len(payload["items"]) == 4
    assert {item["id"] for item in payload["items"]} == {
        "geochange-lite-v2",
        "landcover-lite-v2",
        "geodetect-lite-v2",
        "roadgraph-lite-v2",
    }
    assert {item["task"] for item in payload["items"]} == {
        "change_detection",
        "land_cover",
        "object_detection",
        "road_extraction",
    }
    for card in payload["items"]:
        assert card["reference_metrics"] == {}
        assert card["stage"] == "demo baseline"
        assert card["limitations"]
        assert card["expected_inputs"]
        assert card["metric_scope"]


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
