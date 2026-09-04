from __future__ import annotations

import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image


def test_dataset_catalog_versions_assets_and_runs_registered_input(
    client: TestClient,
    app: FastAPI,
    sample_images: dict[str, bytes],
) -> None:
    creation = client.post(
        "/api/v1/datasets",
        data={
            "name": "  Wuhan   change pair  ",
            "description": "Two registered dates",
            "task_hint": "change_detection",
        },
        files={
            "primary": ("../before.png", sample_images["before"], "image/png"),
            "secondary": ("after.png", sample_images["after"], "image/png"),
        },
    )

    assert creation.status_code == 200
    dataset = creation.json()
    assert dataset["name"] == "Wuhan change pair"
    assert dataset["version"].startswith("sha256:")
    assert dataset["task_hint"] == "change_detection"
    assert dataset["coordinate_space"] == "pixel"
    assert [asset["role"] for asset in dataset["assets"]] == ["primary", "secondary"]
    assert dataset["assets"][0]["name"] == "before.png"
    assert all(len(asset["sha256"]) == 64 for asset in dataset["assets"])

    dataset_root = app.state.settings.artifact_root / "catalog" / dataset["id"]
    persisted = json.loads((dataset_root / "dataset.json").read_text(encoding="utf-8"))
    assert persisted == dataset
    assert (dataset_root / "assets" / "primary.image").is_file()
    assert (dataset_root / "assets" / "secondary.image").is_file()

    summary = client.get("/api/v1/data/summary").json()
    assert summary["registered_datasets"] == 1
    assert summary["registered_assets"] == 2
    assert summary["bytes_total"] == sum(asset["bytes"] for asset in dataset["assets"])
    assert client.get(f"/api/v1/datasets/{dataset['id']}").json() == dataset

    run = client.post(
        f"/api/v1/datasets/{dataset['id']}/runs",
        json={
            "task": "change_detection",
            "model_id": "geochange-lite-v2",
            "threshold": 0.7,
        },
    )
    assert run.status_code == 200
    manifest = client.get(f"/api/v1/jobs/{run.json()['id']}").json()
    assert manifest["status"] == "succeeded"
    expected_source = f"dataset:{dataset['id']}@{dataset['version']}"
    assert {item["source"] for item in manifest["inputs"]} == {expected_source}
    assert [item["sha256"] for item in manifest["inputs"]] == [
        asset["sha256"] for asset in dataset["assets"]
    ]

    filtered = client.get(
        "/api/v1/jobs",
        params={
            "status": "succeeded",
            "task": "change_detection",
            "model_id": "geochange-lite-v2",
        },
    ).json()
    assert [item["id"] for item in filtered] == [manifest["id"]]
    assert client.get("/api/v1/jobs", params={"status": "failed"}).json() == []


def test_dataset_catalog_rejects_mismatched_pair_and_missing_records(
    client: TestClient,
    sample_images: dict[str, bytes],
) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    response = client.post(
        "/api/v1/datasets",
        data={"name": "bad pair", "task_hint": "change_detection"},
        files={
            "primary": ("before.png", sample_images["before"], "image/png"),
            "secondary": ("small.png", buffer.getvalue(), "image/png"),
        },
    )

    assert response.status_code == 400
    assert "identical pixel dimensions" in response.json()["detail"]
    assert client.get("/api/v1/datasets").json() == []
    assert client.get("/api/v1/datasets/unknown").status_code == 404
    assert (
        client.post(
            "/api/v1/datasets/unknown/runs",
            json={"task": "road_extraction", "model_id": "roadgraph-lite-v2"},
        ).status_code
        == 404
    )


def test_folder_dataset_preserves_paths_and_has_stable_content_version(
    client: TestClient,
    app: FastAPI,
    sample_images: dict[str, bytes],
) -> None:
    files = [
        ("files", ("city/train/tile-b.jpg", sample_images["land"], "image/jpeg")),
        ("files", ("city/train/tile-a.png", sample_images["road"], "image/png")),
        ("files", ("city/val/tile-c.png", sample_images["alternate"], "image/png")),
    ]
    creation = client.post(
        "/api/v1/datasets/folder",
        data={
            "name": "City folder",
            "description": "Three versioned tiles",
            "task_hint": "land_cover",
        },
        files=files,
    )

    assert creation.status_code == 200
    dataset = creation.json()
    assert dataset["layout"] == "folder"
    assert dataset["source"] == "folder-upload"
    assert dataset["sample_count"] == 3
    assert [asset["role"] for asset in dataset["assets"]] == ["sample"] * 3
    assert [asset["relative_path"] for asset in dataset["assets"]] == [
        "city/train/tile-a.png",
        "city/train/tile-b.jpg",
        "city/val/tile-c.png",
    ]
    dataset_root = app.state.settings.artifact_root / "catalog" / dataset["id"]
    assert (dataset_root / "assets/city/train/tile-a.png").read_bytes() == sample_images["road"]
    assert (dataset_root / "assets/city/val/tile-c.png").is_file()

    reordered = client.post(
        "/api/v1/datasets/folder",
        data={"name": "Same bytes, another upload", "task_hint": "land_cover"},
        files=list(reversed(files)),
    )
    assert reordered.status_code == 200
    assert reordered.json()["version"] == dataset["version"]

    single_run = client.post(
        f"/api/v1/datasets/{dataset['id']}/runs",
        json={"task": "land_cover", "model_id": "geoseg-lite-v2"},
    )
    assert single_run.status_code == 400
    assert "batch workflow" in single_run.json()["detail"]

    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Do not silently use one tile",
            "dataset_id": dataset["id"],
            "task": "land_cover",
            "model_ids": ["geoseg-lite-v2"],
        },
    )
    assert workflow.status_code == 400
    assert "batch orchestration" in workflow.json()["detail"]


def test_folder_dataset_rejects_unsafe_duplicate_and_excessive_inputs(
    client: TestClient,
    app: FastAPI,
    sample_images: dict[str, bytes],
) -> None:
    catalog = app.state.catalog
    with pytest.raises(ValueError, match="Unsafe dataset path"):
        catalog.create_folder_dataset(
            name="unsafe",
            description="",
            task_hint=None,
            files=[("../escape.png", sample_images["road"])],
        )
    with pytest.raises(ValueError, match="Duplicate dataset path"):
        catalog.create_folder_dataset(
            name="duplicates",
            description="",
            task_hint=None,
            files=[
                ("tiles/A.png", sample_images["road"]),
                ("tiles/a.png", sample_images["alternate"]),
            ],
        )

    too_many = [
        ("files", (f"folder/{index}.png", sample_images["road"], "image/png"))
        for index in range(app.state.settings.max_dataset_files + 1)
    ]
    response = client.post(
        "/api/v1/datasets/folder",
        data={"name": "too many"},
        files=too_many,
    )
    assert response.status_code == 413
    assert "file limit" in response.json()["detail"]
    assert not (app.state.settings.artifact_root / "catalog" / "escape.png").exists()
