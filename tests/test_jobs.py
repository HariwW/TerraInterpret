from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from PIL import Image

from i2rsi.service import JobService
from i2rsi.settings import Settings

ACCURACY_METRIC = re.compile(
    r"(^|_)(accuracy|iou|miou|f1|precision|recall|map|auc|kappa)($|_)",
    re.IGNORECASE,
)


def _assert_no_unlabelled_accuracy_claim(metrics: dict[str, object]) -> None:
    for key in metrics:
        normalised = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        assert ACCURACY_METRIC.search(normalised) is None, key


def test_demo_archive_accepts_top_level_data_demo_directory(
    settings: Settings,
    sample_images: dict[str, bytes],
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "prefixed-demo.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data_demo/CD/test_1_A.png", sample_images["before"])
        archive.writestr("data_demo/CD/test_1_B.png", sample_images["after"])

    service = JobService(replace(settings, demo_archive=archive_path))
    before, name = service.read_demo_asset("cd-before")

    assert before == sample_images["before"]
    assert name == "test_1_A.png"


@pytest.mark.parametrize(
    (
        "scenario_id",
        "task",
        "model_id",
        "expected_input_count",
        "expected_artifacts",
        "expected_parameters",
    ),
    [
        (
            "urban-change",
            "change_detection",
            "geochange-robust-v3",
            2,
            {"original", "secondary", "overlay", "mask", "uncertainty", "features"},
            {"threshold": 0.731},
        ),
        (
            "land-cover-mapping",
            "land_cover",
            "landcover-lite-v2",
            1,
            {"original", "overlay", "mask", "uncertainty", "features"},
            {},
        ),
        (
            "aircraft-proposals",
            "object_detection",
            "geodetect-lite-v2",
            1,
            {"original", "overlay", "mask", "uncertainty", "features"},
            {},
        ),
        (
            "road-network",
            "road_extraction",
            "roadgraph-lite-v2",
            1,
            {"original", "overlay", "mask", "uncertainty", "features"},
            {"threshold": 0.731},
        ),
    ],
)
def test_demo_run_produces_auditable_artifacts(
    client: TestClient,
    app: FastAPI,
    scenario_id: str,
    task: str,
    model_id: str,
    expected_input_count: int,
    expected_artifacts: set[str],
    expected_parameters: dict[str, float],
) -> None:
    creation = client.post(f"/api/v1/demo-runs/{scenario_id}?threshold=0.731")

    assert creation.status_code == 200
    job_id = creation.json()["id"]
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    manifest = response.json()

    assert manifest["status"] == "succeeded", manifest.get("error")
    assert manifest["task"] == task
    assert manifest["model_id"] == model_id
    assert manifest["parameters"] == expected_parameters
    assert len(manifest["inputs"]) == expected_input_count
    assert all(item["source"] == f"bundled-demo:{scenario_id}" for item in manifest["inputs"])
    assert all(len(item["sha256"]) == 64 for item in manifest["inputs"])

    artifact_by_kind = {artifact["kind"]: artifact for artifact in manifest["artifacts"]}
    assert set(artifact_by_kind) == expected_artifacts
    for artifact in manifest["artifacts"]:
        assert artifact["url"].startswith(f"/artifacts/jobs/{job_id}/outputs/")
        assert ".." not in artifact["url"]
        download = client.get(artifact["url"])
        assert download.status_code == 200
        assert hashlib.sha256(download.content).hexdigest() == artifact["sha256"]
        if artifact["kind"] != "features":
            assert download.headers["content-type"].startswith(artifact["media_type"])

    features = client.get(artifact_by_kind["features"]["url"])
    feature_collection = features.json()
    assert feature_collection["type"] == "FeatureCollection"
    assert isinstance(feature_collection["features"], list)

    assert len(manifest["histogram"]) == 10
    assert (
        sum(manifest["histogram"])
        == manifest["metrics"]["width_px"] * manifest["metrics"]["height_px"]
    )
    assert manifest["legend"]
    assert manifest["summary"]
    _assert_no_unlabelled_accuracy_claim(manifest["metrics"])

    provenance = manifest["provenance"]
    if model_id == "geochange-robust-v3":
        assert provenance["engine"] == "robust-change-cpu"
        assert provenance["engine_version"] == "3.0.0"
        assert provenance["backend"] == "builtin-robust-change"
    else:
        assert provenance["engine"] == "transparent-cpu-baselines"
        assert provenance["engine_version"] == "2.0.0"
    assert provenance["model_id"] == model_id
    assert provenance["task"] == task
    assert provenance["parameters"] == manifest["parameters"]
    assert provenance["input_sha256"] == [item["sha256"] for item in manifest["inputs"]]
    assert provenance["reproducibility"] == "deterministic CPU baseline"
    assert "ground truth" in provenance["claim_boundary"].lower()

    manifest_path = app.state.settings.artifact_root / "jobs" / job_id / "manifest.json"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted == manifest


def test_demo_bootstrap_builds_and_reuses_one_job_per_task(client: TestClient) -> None:
    first = client.post("/api/v1/demo-runs/bootstrap")

    assert first.status_code == 200
    created = first.json()
    assert len(created) == 4
    assert {item["task"] for item in created} == {
        "change_detection",
        "land_cover",
        "object_detection",
        "road_extraction",
    }
    completed = [client.get(f"/api/v1/jobs/{item['id']}").json() for item in created]
    assert all(item["status"] == "succeeded" for item in completed)

    second = client.post("/api/v1/demo-runs/bootstrap")

    assert second.status_code == 200
    assert [item["id"] for item in second.json()] == [item["id"] for item in completed]
    assert len(client.get("/api/v1/jobs?limit=100").json()) == 4


def test_geojson_download_uses_manifest_media_type(client: TestClient) -> None:
    creation = client.post("/api/v1/demo-runs/land-cover-mapping")
    manifest = client.get(f"/api/v1/jobs/{creation.json()['id']}").json()
    artifact = next(item for item in manifest["artifacts"] if item["kind"] == "features")

    response = client.get(artifact["url"])

    assert response.headers["content-type"].startswith(artifact["media_type"])


def _post_land_cover(
    client: TestClient,
    payload: bytes,
    filename: str = "scene.png",
    threshold: str = "0.62",
) -> Response:
    return client.post(
        "/api/v1/jobs",
        data={
            "task": "land_cover",
            "model_id": "landcover-lite-v2",
            "threshold": threshold,
        },
        files={"primary": (filename, payload, "image/png")},
    )


def test_upload_validation_rejects_bad_requests_without_creating_jobs(
    client: TestClient,
    app: FastAPI,
    sample_images: dict[str, bytes],
) -> None:
    missing_file = client.post(
        "/api/v1/jobs",
        data={"task": "land_cover", "model_id": "landcover-lite-v2"},
    )
    empty_file = _post_land_cover(client, b"")
    oversized = _post_land_cover(client, b"x" * (app.state.settings.max_upload_bytes + 1))
    unknown_model = client.post(
        "/api/v1/jobs",
        data={"task": "land_cover", "model_id": "not-a-model"},
        files={"primary": ("scene.png", sample_images["land"], "image/png")},
    )
    wrong_model = client.post(
        "/api/v1/jobs",
        data={"task": "land_cover", "model_id": "geochange-lite-v2"},
        files={"primary": ("scene.png", sample_images["land"], "image/png")},
    )
    missing_second_image = client.post(
        "/api/v1/jobs",
        data={"task": "change_detection", "model_id": "geochange-lite-v2"},
        files={"primary": ("before.png", sample_images["before"], "image/png")},
    )
    invalid_task = client.post(
        "/api/v1/jobs",
        data={"task": "segmentation", "model_id": "landcover-lite-v2"},
        files={"primary": ("scene.png", sample_images["land"], "image/png")},
    )
    invalid_threshold = _post_land_cover(client, sample_images["land"], threshold="0.99")

    assert missing_file.status_code == 422
    assert empty_file.status_code == 400
    assert "empty" in empty_file.json()["detail"].lower()
    assert oversized.status_code == 413
    assert unknown_model.status_code == 400
    assert "Unknown model" in unknown_model.json()["detail"]
    assert wrong_model.status_code == 400
    assert "does not support" in wrong_model.json()["detail"]
    assert missing_second_image.status_code == 400
    assert "requires two images" in missing_second_image.json()["detail"]
    assert invalid_task.status_code == 422
    assert invalid_threshold.status_code == 422
    assert client.get("/api/v1/jobs").json() == []
    assert not any((app.state.settings.artifact_root / "jobs").iterdir())


def test_unreadable_upload_is_rejected_before_job_creation(client: TestClient) -> None:
    creation = _post_land_cover(client, b"this is not an image", "corrupt.png")

    assert creation.status_code == 400
    assert "not a valid PNG or JPEG" in creation.json()["detail"]
    assert client.get("/api/v1/jobs").json() == []


def test_jobs_are_isolated_and_upload_names_are_sanitised(
    client: TestClient,
    app: FastAPI,
    sample_images: dict[str, bytes],
) -> None:
    first = _post_land_cover(client, sample_images["land"], "../../first-scene.png")
    second = _post_land_cover(client, sample_images["alternate"], "second-scene.png")

    assert first.status_code == second.status_code == 200
    first_manifest = client.get(f"/api/v1/jobs/{first.json()['id']}").json()
    second_manifest = client.get(f"/api/v1/jobs/{second.json()['id']}").json()
    assert first_manifest["status"] == second_manifest["status"] == "succeeded"
    assert first_manifest["id"] != second_manifest["id"]
    assert first_manifest["inputs"][0]["name"] == "first-scene.png"
    assert second_manifest["inputs"][0]["name"] == "second-scene.png"
    assert first_manifest["inputs"][0]["sha256"] != second_manifest["inputs"][0]["sha256"]

    first_prefix = f"/artifacts/jobs/{first_manifest['id']}/outputs/"
    second_prefix = f"/artifacts/jobs/{second_manifest['id']}/outputs/"
    assert all(item["url"].startswith(first_prefix) for item in first_manifest["artifacts"])
    assert all(item["url"].startswith(second_prefix) for item in second_manifest["artifacts"])
    assert not (
        {item["url"] for item in first_manifest["artifacts"]}
        & {item["url"] for item in second_manifest["artifacts"]}
    )

    jobs_root = app.state.settings.artifact_root / "jobs"
    assert {path.name for path in jobs_root.iterdir()} == {
        first_manifest["id"],
        second_manifest["id"],
    }
    for manifest in (first_manifest, second_manifest):
        job_root = jobs_root / manifest["id"]
        assert (job_root / "inputs" / "primary.image").is_file()
        assert (job_root / "outputs" / "original.png").is_file()
        assert not (job_root / "inputs" / manifest["inputs"][0]["name"]).exists()
        assert (
            client.get(f"/artifacts/jobs/{manifest['id']}/inputs/primary.image").status_code == 404
        )

    first_original_url = next(
        item["url"] for item in first_manifest["artifacts"] if item["kind"] == "original"
    )
    second_original_url = next(
        item["url"] for item in second_manifest["artifacts"] if item["kind"] == "original"
    )
    first_image = Image.open(Path(jobs_root / first_manifest["id"] / "outputs/original.png"))
    second_image = Image.open(Path(jobs_root / second_manifest["id"] / "outputs/original.png"))
    assert first_image.getpixel((48, 36)) != second_image.getpixel((48, 36))
    assert client.get(first_original_url).content != client.get(second_original_url).content

    listed = client.get("/api/v1/jobs?limit=2").json()
    assert {item["id"] for item in listed} == {first_manifest["id"], second_manifest["id"]}
