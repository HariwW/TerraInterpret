from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    artifact_root: Path
    static_root: Path
    demo_archive: Path
    max_upload_bytes: int = 32 * 1024 * 1024
    max_dataset_bytes: int = 512 * 1024 * 1024
    max_dataset_files: int = 1000
    max_image_edge: int = 1536
    max_image_pixels: int = 64_000_000
    job_retention: int = 100
    agent_enabled: bool = True
    agent_provider: str | None = None
    agent_model: str | None = None
    model_runtime_python: Path | None = None
    model_cache_root: Path | None = None

    @classmethod
    def from_environment(cls) -> Settings:
        project_root = Path(__file__).resolve().parent.parent
        artifact_root = Path(
            os.environ.get("I2RSI_ARTIFACT_ROOT", project_root / "artifacts" / "v2")
        ).resolve()
        model_runtime = Path(
            os.environ.get(
                "TERRAINTERPRET_MODEL_PYTHON",
                project_root / ".venv-models" / "bin" / "python",
            )
        ).expanduser()
        model_cache = Path(
            os.environ.get("TERRAINTERPRET_MODEL_CACHE", artifact_root / "model-cache")
        ).resolve()
        return cls(
            project_root=project_root,
            artifact_root=artifact_root,
            static_root=project_root / "i2rsi" / "static",
            demo_archive=project_root / "data_demo.zip",
            max_upload_bytes=int(os.environ.get("I2RSI_MAX_UPLOAD_MB", "32")) * 1024 * 1024,
            max_dataset_bytes=int(os.environ.get("I2RSI_MAX_DATASET_MB", "512"))
            * 1024
            * 1024,
            max_dataset_files=int(os.environ.get("I2RSI_MAX_DATASET_FILES", "1000")),
            max_image_edge=int(os.environ.get("I2RSI_MAX_IMAGE_EDGE", "1536")),
            agent_enabled=os.environ.get("I2RSI_AGENT_ENABLED", "1").lower()
            not in {"0", "false", "no"},
            agent_provider=os.environ.get("I2RSI_AGENT_PROVIDER") or None,
            agent_model=os.environ.get("I2RSI_AGENT_MODEL") or None,
            model_runtime_python=model_runtime,
            model_cache_root=model_cache,
        )
