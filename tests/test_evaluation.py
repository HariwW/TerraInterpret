from __future__ import annotations

import io
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image


def _completed_demo(client: TestClient, scenario_id: str) -> dict:
    creation = client.post(f"/api/v1/demo-runs/{scenario_id}")
    assert creation.status_code == 200
    job = client.get(f"/api/v1/jobs/{creation.json()['id']}").json()
    assert job["status"] == "succeeded"
    return job


def test_binary_segmentation_evaluation_is_bound_to_ground_truth_and_persisted(
    client: TestClient,
    app: FastAPI,
) -> None:
    job = _completed_demo(client, "road-network")
    mask = next(artifact for artifact in job["artifacts"] if artifact["kind"] == "mask")
    prediction = client.get(mask["url"]).content

    response = client.post(
        "/api/v1/evaluations",
        data={"job_id": job["id"], "positive_threshold": "127"},
        files={"ground_truth": ("reviewed-mask.png", prediction, "image/png")},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["job_id"] == job["id"]
    assert report["task"] == "road_extraction"
    assert report["model_id"] == "roadgraph-lite-v2"
    assert report["metric_suite"] == "binary-segmentation-v1"
    assert report["ground_truth_name"] == "reviewed-mask.png"
    assert report["prediction_sha256"] == mask["sha256"]
    assert report["pixel_count"] == job["metrics"]["width_px"] * job["metrics"]["height_px"]
    assert all(
        report["metrics"][metric] == 1.0
        for metric in ("iou", "f1", "precision", "recall", "accuracy")
    )
    if report["confusion"]["tn"] + report["confusion"]["fp"] == 0:
        assert report["metrics"]["specificity"] is None
    else:
        assert report["metrics"]["specificity"] == 1.0
    assert report["confusion"]["fp"] == report["confusion"]["fn"] == 0
    assert "uploaded ground truth" in report["claim_scope"]
    assert "reported as null" in report["claim_scope"]

    report_path = app.state.settings.artifact_root / "evaluations" / report["id"] / "report.json"
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert report_path.with_name("ground_truth.png").is_file()
    assert client.get(f"/api/v1/evaluations/{report['id']}").json() == report
    assert client.get("/api/v1/evaluations").json() == [report]


def test_evaluation_rejects_unsupported_task_and_wrong_mask_shape(
    client: TestClient,
) -> None:
    object_job = _completed_demo(client, "aircraft-proposals")
    unsupported = client.post(
        "/api/v1/evaluations",
        data={"job_id": object_job["id"]},
        files={"ground_truth": ("truth.png", b"not used", "image/png")},
    )
    assert unsupported.status_code == 400
    assert "change detection and road extraction only" in unsupported.json()["detail"]

    road_job = _completed_demo(client, "road-network")
    small = io.BytesIO()
    Image.new("L", (20, 20), 255).save(small, format="PNG")
    mismatch = client.post(
        "/api/v1/evaluations",
        data={"job_id": road_job["id"]},
        files={"ground_truth": ("small.png", small.getvalue(), "image/png")},
    )
    assert mismatch.status_code == 400
    assert "dimensions must match" in mismatch.json()["detail"]
    assert client.get("/api/v1/evaluations/not-found").status_code == 404
