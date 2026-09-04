from __future__ import annotations

from fastapi.testclient import TestClient


def _register_dataset(
    client: TestClient,
    image: bytes,
    *,
    task: str,
    secondary: bytes | None = None,
) -> dict:
    files = {"primary": ("primary.png", image, "image/png")}
    if secondary is not None:
        files["secondary"] = ("secondary.png", secondary, "image/png")
    response = client.post(
        "/api/v1/datasets",
        data={"name": f"{task} workflow", "task_hint": task},
        files=files,
    )
    assert response.status_code == 200
    return response.json()


def test_binary_workflow_runs_and_waits_for_shared_ground_truth(
    client: TestClient, sample_images: dict[str, bytes], app
) -> None:
    dataset = _register_dataset(
        client,
        sample_images["road"],
        task="road_extraction",
    )
    created = client.post(
        "/api/v1/workflows",
        json={
            "name": "Road benchmark",
            "dataset_id": dataset["id"],
            "task": "road_extraction",
            "model_ids": ["roadgraph-lite-v2"],
            "model_parameters": {"roadgraph-lite-v2": {"threshold": 0.71}},
        },
    )
    assert created.status_code == 200
    plan = created.json()
    assert plan["status"] == "planned"
    assert "threshold" not in plan
    assert plan["model_parameters"] == {"roadgraph-lite-v2": {"threshold": 0.71}}
    assert [step["kind"] for step in plan["steps"]] == [
        "validation",
        "inference",
        "evaluation",
        "summary",
    ]

    queued = client.post(f"/api/v1/workflows/{plan['id']}/execute")
    assert queued.status_code == 200
    completed = client.get(f"/api/v1/workflows/{plan['id']}").json()
    assert completed["status"] == "awaiting_ground_truth"
    assert len(completed["job_ids"]) == 1
    assert completed["summary"]["successful_runs"] == 1
    job = client.get(f"/api/v1/jobs/{completed['job_ids'][0]}").json()
    assert job["parameters"] == {"threshold": 0.71}
    evaluation_step = next(step for step in completed["steps"] if step["kind"] == "evaluation")
    assert evaluation_step["status"] == "blocked"

    job_id = completed["job_ids"][0]
    truth = (app.state.service.jobs_root / job_id / "outputs" / "mask.png").read_bytes()
    evaluated = client.post(
        f"/api/v1/workflows/{plan['id']}/evaluations",
        data={"positive_threshold": "127"},
        files={"ground_truth": ("truth.png", truth, "image/png")},
    )
    assert evaluated.status_code == 200
    result = evaluated.json()
    assert result["status"] == "succeeded"
    assert len(result["evaluation_ids"]) == 1
    assert result["summary"]["ranking"][0]["model_id"] == "roadgraph-lite-v2"
    assert result["summary"]["ranking"][0]["f1"] == 1.0


def test_non_binary_workflow_finishes_without_evaluation(
    client: TestClient, sample_images: dict[str, bytes]
) -> None:
    dataset = _register_dataset(
        client,
        sample_images["objects"],
        task="object_detection",
    )
    created = client.post(
        "/api/v1/workflows",
        json={
            "dataset_id": dataset["id"],
            "task": "object_detection",
            "model_ids": ["geodetect-lite-v2"],
        },
    ).json()
    response = client.post(f"/api/v1/workflows/{created['id']}/execute")
    assert response.status_code == 200
    result = client.get(f"/api/v1/workflows/{created['id']}").json()
    assert result["status"] == "succeeded"
    assert all(step["kind"] != "evaluation" for step in result["steps"])


def test_workflow_rejects_dataset_task_mismatch(
    client: TestClient, sample_images: dict[str, bytes]
) -> None:
    dataset = _register_dataset(
        client,
        sample_images["road"],
        task="road_extraction",
    )
    response = client.post(
        "/api/v1/workflows",
        json={
            "dataset_id": dataset["id"],
            "task": "land_cover",
            "model_ids": ["landcover-lite-v2"],
        },
    )
    assert response.status_code == 400
    assert "task hint" in response.json()["detail"]


def test_workflow_rejects_parameters_not_declared_by_model(
    client: TestClient, sample_images: dict[str, bytes]
) -> None:
    dataset = _register_dataset(
        client,
        sample_images["objects"],
        task="object_detection",
    )
    response = client.post(
        "/api/v1/workflows",
        json={
            "dataset_id": dataset["id"],
            "task": "object_detection",
            "model_ids": ["geodetect-lite-v2"],
            "model_parameters": {"geodetect-lite-v2": {"threshold": 0.5}},
        },
    )

    assert response.status_code == 400
    assert "Unsupported parameters" in response.json()["detail"]
