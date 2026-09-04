from __future__ import annotations

import hashlib
import json
import shutil
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError

from .engine import sha256_file
from .models import DataAssetRecord, DatasetRecord, TaskType
from .settings import Settings


class DatasetNotFoundError(KeyError):
    pass


class DataCatalogService:
    """Small persistent catalog for local, pixel-space research datasets."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.artifact_root / "catalog"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._datasets: dict[str, DatasetRecord] = {}
        self._load_existing()

    def create_dataset(
        self,
        *,
        name: str,
        description: str,
        task_hint: TaskType | None,
        primary: bytes,
        primary_name: str,
        secondary: bytes | None = None,
        secondary_name: str | None = None,
    ) -> DatasetRecord:
        clean_name = " ".join(name.split()).strip()
        if not clean_name:
            raise ValueError("Dataset name is required")
        primary_meta = self._validate_image(primary)
        secondary_meta = self._validate_image(secondary) if secondary is not None else None
        if secondary_meta and (
            primary_meta["width_px"],
            primary_meta["height_px"],
        ) != (
            secondary_meta["width_px"],
            secondary_meta["height_px"],
        ):
            raise ValueError("Paired dataset images must have identical pixel dimensions")

        dataset_id = uuid.uuid4().hex
        dataset_dir = self.root / dataset_id
        assets_dir = dataset_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=False)
        primary_path = assets_dir / "primary.image"
        primary_path.write_bytes(primary)
        assets = [self._asset_record(primary_path, primary_name, "primary", primary_meta)]
        if secondary is not None:
            secondary_path = assets_dir / "secondary.image"
            secondary_path.write_bytes(secondary)
            assets.append(
                self._asset_record(
                    secondary_path,
                    secondary_name or "secondary.image",
                    "secondary",
                    secondary_meta or {},
                )
            )

        digest = hashlib.sha256(
            "|".join(f"{item.role}:{item.sha256}" for item in assets).encode()
        ).hexdigest()
        record = DatasetRecord(
            id=dataset_id,
            version=f"sha256:{digest[:16]}",
            name=clean_name[:120],
            description=description.strip()[:500],
            task_hint=task_hint,
            coordinate_space="pixel",
            source="local-upload",
            layout="paired" if secondary is not None else "single",
            sample_count=1,
            assets=assets,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._datasets[dataset_id] = record
            self._persist(record)
        return record.model_copy(deep=True)

    def create_folder_dataset(
        self,
        *,
        name: str,
        description: str,
        task_hint: TaskType | None,
        files: Sequence[tuple[str, bytes]],
    ) -> DatasetRecord:
        clean_name = " ".join(name.split()).strip()
        if not clean_name:
            raise ValueError("Dataset name is required")
        if not files:
            raise ValueError("Dataset folder contains no PNG or JPEG images")
        if len(files) > self.settings.max_dataset_files:
            raise ValueError(
                f"Dataset folder exceeds the {self.settings.max_dataset_files}-file limit"
            )

        validated: list[tuple[str, bytes, dict[str, int | str]]] = []
        seen_paths: set[str] = set()
        total_bytes = 0
        for supplied_path, payload in files:
            relative_path = self._normalise_relative_path(supplied_path)
            path_key = relative_path.casefold()
            if path_key in seen_paths:
                raise ValueError(f"Duplicate dataset path: {relative_path}")
            seen_paths.add(path_key)
            total_bytes += len(payload)
            if total_bytes > self.settings.max_dataset_bytes:
                limit_mb = self.settings.max_dataset_bytes // (1024 * 1024)
                raise ValueError(f"Dataset folder exceeds the {limit_mb} MB total limit")
            validated.append((relative_path, payload, self._validate_image(payload)))

        # Browser selection order is not stable across platforms. Sorting makes the
        # content version reproducible for the same directory tree.
        validated.sort(key=lambda item: (item[0].casefold(), item[0]))
        dataset_id = uuid.uuid4().hex
        dataset_dir = self.root / dataset_id
        assets_dir = dataset_dir / "assets"
        assets: list[DataAssetRecord] = []
        try:
            assets_dir.mkdir(parents=True, exist_ok=False)
            for relative_path, payload, image_meta in validated:
                target = assets_dir.joinpath(*PurePosixPath(relative_path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                assets.append(
                    self._asset_record(
                        target,
                        PurePosixPath(relative_path).name,
                        "sample",
                        image_meta,
                        relative_path=relative_path,
                    )
                )

            digest = hashlib.sha256(
                "|".join(f"{item.relative_path}:{item.sha256}" for item in assets).encode()
            ).hexdigest()
            record = DatasetRecord(
                id=dataset_id,
                version=f"sha256:{digest[:16]}",
                name=clean_name[:120],
                description=description.strip()[:500],
                task_hint=task_hint,
                coordinate_space="pixel",
                source="folder-upload",
                layout="folder",
                sample_count=len(assets),
                assets=assets,
                created_at=datetime.now(UTC),
            )
            with self._lock:
                self._datasets[dataset_id] = record
                try:
                    self._persist(record)
                except Exception:
                    self._datasets.pop(dataset_id, None)
                    raise
            return record.model_copy(deep=True)
        except Exception:
            shutil.rmtree(dataset_dir, ignore_errors=True)
            raise

    def list_datasets(self, limit: int = 100) -> list[DatasetRecord]:
        with self._lock:
            records = sorted(
                self._datasets.values(),
                key=lambda item: item.created_at,
                reverse=True,
            )[:limit]
            return [item.model_copy(deep=True) for item in records]

    def get_dataset(self, dataset_id: str) -> DatasetRecord:
        with self._lock:
            record = self._datasets.get(dataset_id)
            if record is None:
                raise DatasetNotFoundError(dataset_id)
            return record.model_copy(deep=True)

    def read_inputs(self, dataset_id: str) -> tuple[bytes, str, bytes | None, str | None]:
        record = self.get_dataset(dataset_id)
        if record.layout == "folder":
            raise ValueError(
                "Folder datasets require a batch workflow and cannot use the "
                "single-scene run endpoint"
            )
        dataset_dir = self.root / record.id / "assets"
        primary_meta = next(item for item in record.assets if item.role == "primary")
        secondary_meta = next(
            (item for item in record.assets if item.role == "secondary"),
            None,
        )
        primary = (dataset_dir / "primary.image").read_bytes()
        secondary_path = dataset_dir / "secondary.image"
        secondary = secondary_path.read_bytes() if secondary_meta else None
        return (
            primary,
            primary_meta.name,
            secondary,
            secondary_meta.name if secondary_meta else None,
        )

    def summary(self, bundled_demo_count: int) -> dict[str, int | str]:
        records = self.list_datasets()
        bytes_total = sum(asset.bytes for record in records for asset in record.assets)
        return {
            "registered_datasets": len(records),
            "registered_assets": sum(len(record.assets) for record in records),
            "bytes_total": bytes_total,
            "bundled_demo_scenarios": bundled_demo_count,
            "coordinate_space": "pixel",
        }

    def _validate_image(self, payload: bytes | None) -> dict[str, int | str]:
        if not payload:
            raise ValueError("Dataset image is empty")
        if len(payload) > self.settings.max_upload_bytes:
            raise ValueError("Dataset image exceeds the configured upload limit")
        try:
            with Image.open(BytesIO(payload)) as image:
                image_format = image.format
                width, height = image.size
                if image_format not in {"PNG", "JPEG"}:
                    raise ValueError("Only PNG and JPEG dataset images are accepted")
                if width * height > self.settings.max_image_pixels:
                    raise ValueError("Decoded dataset image exceeds the pixel limit")
                image.verify()
        except ValueError:
            raise
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError("Dataset asset is not a valid PNG or JPEG image") from exc
        return {"format": image_format, "width_px": width, "height_px": height}

    @staticmethod
    def _asset_record(
        path: Path,
        name: str,
        role: str,
        image_meta: dict[str, int | str],
        *,
        relative_path: str | None = None,
    ) -> DataAssetRecord:
        image_format = str(image_meta.get("format", "PNG"))
        return DataAssetRecord(
            role=role,
            name=Path(name).name[:160] or f"{role}.image",
            relative_path=relative_path,
            media_type="image/png" if image_format == "PNG" else "image/jpeg",
            bytes=path.stat().st_size,
            sha256=sha256_file(path),
            width_px=int(image_meta["width_px"]),
            height_px=int(image_meta["height_px"]),
        )

    @staticmethod
    def _normalise_relative_path(value: str) -> str:
        candidate = value.replace("\\", "/").strip()
        path = PurePosixPath(candidate)
        if (
            not candidate
            or candidate in {".", ".."}
            or candidate.startswith("/")
            or "\x00" in candidate
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(f"Unsafe dataset path: {value!r}")
        normalised = path.as_posix()
        if len(normalised) > 500:
            raise ValueError("Dataset relative path exceeds 500 characters")
        return normalised

    def _persist(self, record: DatasetRecord) -> None:
        dataset_dir = self.root / record.id
        target = dataset_dir / "dataset.json"
        temporary = dataset_dir / ".dataset.tmp"
        temporary.write_text(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _load_existing(self) -> None:
        for path in self.root.glob("*/dataset.json"):
            try:
                record = DatasetRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self._datasets[record.id] = record
