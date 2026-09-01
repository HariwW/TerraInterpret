from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from i2rsi.geoadapt import GeoAdaptService


def _create_object_review_queue(client: TestClient) -> tuple[dict[str, object], list[dict]]:
    creation = client.post("/api/v1/demo-runs/aircraft-proposals")
    assert creation.status_code == 200
    job = client.get(f"/api/v1/jobs/{creation.json()['id']}").json()
    assert job["status"] == "succeeded"
    reviews = client.get(
        f"/api/v1/geoadapt/reviews?job_id={job['id']}&limit=100"
    ).json()
    return job, reviews


def test_jobs_enter_uncertainty_diversity_review_queue(
    client: TestClient, app: FastAPI
) -> None:
    job, reviews = _create_object_review_queue(client)

    assert len(reviews) >= 4
    assert len({review["id"] for review in reviews}) == len(reviews)
    assert all(review["status"] == "pending" for review in reviews)
    assert all(0 <= review["uncertainty_score"] <= 1 for review in reviews)
    assert all(0 <= review["diversity_score"] <= 1 for review in reviews)
    assert all(0 <= review["acquisition_score"] <= 1 for review in reviews)
    assert reviews[0]["acquisition_score"] >= reviews[-1]["acquisition_score"]

    persisted_job = client.get(f"/api/v1/jobs/{job['id']}").json()
    geoadapt = persisted_job["provenance"]["geoadapt"]
    assert geoadapt["status"] == "queued_for_review"
    assert geoadapt["review_candidate_count"] == len(reviews)
    assert geoadapt["acquisition"] == "uncertainty-diversity-v1"

    candidates_path = app.state.settings.artifact_root / "geoadapt/review_candidates.json"
    persisted = json.loads(candidates_path.read_text(encoding="utf-8"))
    assert {item["id"] for item in persisted} == {item["id"] for item in reviews}


def test_annotation_events_are_validated_append_only_and_versioned(
    client: TestClient, app: FastAPI
) -> None:
    _, reviews = _create_object_review_queue(client)
    candidate = reviews[0]

    invalid = client.post(
        f"/api/v1/geoadapt/reviews/{candidate['id']}/annotations",
        json={
            "decision": "correct",
            "label": "aircraft",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [999, 0], [999, 999], [0, 0]]],
            },
        },
    )
    assert invalid.status_code == 400
    assert "outside" in invalid.json()["detail"]

    accepted = client.post(
        f"/api/v1/geoadapt/reviews/{candidate['id']}/annotations",
        json={"decision": "accept", "reviewer": "reviewer-a", "notes": "looks valid"},
    )
    assert accepted.status_code == 200
    first = accepted.json()
    assert first["candidate_version"] == 1
    assert first["parent_event_id"] is None
    assert len(first["sha256"]) == 64
    assert first["dataset_version"].endswith("v0001")

    rejected = client.post(
        f"/api/v1/geoadapt/reviews/{candidate['id']}/annotations",
        json={"decision": "reject", "notes": "false positive"},
    )
    assert rejected.status_code == 200
    second = rejected.json()
    assert second["candidate_version"] == 2
    assert second["parent_event_id"] == first["id"]
    assert second["label"] == "background"
    assert second["sha256"] != first["sha256"]

    event_root = app.state.settings.artifact_root / "geoadapt/annotation_events"
    first_path = event_root / f"{first['id']}.json"
    second_path = event_root / f"{second['id']}.json"
    assert first_path.is_file() and second_path.is_file()
    assert json.loads(first_path.read_text(encoding="utf-8"))["sha256"] == first["sha256"]
    assert json.loads(second_path.read_text(encoding="utf-8"))["sha256"] == second["sha256"]
    assert client.get(f"/api/v1/geoadapt/reviews/{candidate['id']}").json()[
        "status"
    ] == "rejected"


def test_review_feedback_fits_calibrator_and_survives_reload(
    client: TestClient, app: FastAPI
) -> None:
    _, reviews = _create_object_review_queue(client)
    selected = reviews[:4]
    before = {item["id"]: item["uncertainty_score"] for item in reviews[4:]}

    for index, candidate in enumerate(selected):
        decision = "accept" if index % 2 == 0 else "reject"
        response = client.post(
            f"/api/v1/geoadapt/reviews/{candidate['id']}/annotations",
            json={"decision": decision, "reviewer": "loop-test"},
        )
        assert response.status_code == 200

    too_large = client.post(
        "/api/v1/geoadapt/adaptations",
        json={
            "task": "object_detection",
            "model_id": "geodetect-lite-v2",
            "min_samples": 5,
        },
    )
    assert too_large.status_code == 400

    adaptation = client.post(
        "/api/v1/geoadapt/adaptations",
        json={
            "task": "object_detection",
            "model_id": "geodetect-lite-v2",
            "min_samples": 4,
        },
    )
    assert adaptation.status_code == 200
    round_result = adaptation.json()
    assert round_result["method"] == "proxy-logistic-calibration-v1"
    assert round_result["sample_count"] == 4
    assert round_result["positive_count"] == round_result["negative_count"] == 2
    assert len(round_result["annotation_sha256"]) == 64
    assert "not GeoFM" in round_result["claim_boundary"]

    pending = client.get(
        "/api/v1/geoadapt/reviews?task=object_detection&limit=100"
    ).json()
    after = {item["id"]: item["uncertainty_score"] for item in pending}
    assert set(after) == set(before)
    assert any(after[candidate_id] != score for candidate_id, score in before.items())

    state = client.get("/api/v1/geoadapt/state").json()
    assert state["loop_complete"] is True
    assert state["annotation_events"] == 4
    assert state["adaptation_rounds"] == 1
    assert state["capabilities"]["proxy_calibration_feedback"] == "implemented"
    assert "backend contract" in state["capabilities"]["geofm_peft"]

    reloaded = GeoAdaptService(app.state.settings.artifact_root / "geoadapt")
    reloaded_state = reloaded.state()
    assert reloaded_state.annotation_events == 4
    assert reloaded_state.adaptation_rounds == 1
    assert reloaded_state.loop_complete is True
    assert reloaded.list_adaptations()[0].id == round_result["id"]


def test_adaptation_rejects_single_class_feedback(client: TestClient) -> None:
    _, reviews = _create_object_review_queue(client)
    for candidate in reviews[:4]:
        response = client.post(
            f"/api/v1/geoadapt/reviews/{candidate['id']}/annotations",
            json={"decision": "accept"},
        )
        assert response.status_code == 200

    adaptation = client.post(
        "/api/v1/geoadapt/adaptations",
        json={
            "task": "object_detection",
            "model_id": "geodetect-lite-v2",
            "min_samples": 4,
        },
    )
    assert adaptation.status_code == 400
    assert "both positive" in adaptation.json()["detail"]
