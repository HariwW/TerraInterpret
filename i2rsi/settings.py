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
    max_image_edge: int = 1536
    max_image_pixels: int = 64_000_000
    job_retention: int = 100

    @classmethod
    def from_environment(cls) -> Settings:
        project_root = Path(__file__).resolve().parent.parent
        artifact_root = Path(
            os.environ.get("I2RSI_ARTIFACT_ROOT", project_root / "artifacts" / "v2")
        ).resolve()
        return cls(
            project_root=project_root,
            artifact_root=artifact_root,
            static_root=project_root / "i2rsi" / "static",
            demo_archive=project_root / "data_demo.zip",
            max_upload_bytes=int(os.environ.get("I2RSI_MAX_UPLOAD_MB", "32")) * 1024 * 1024,
            max_image_edge=int(os.environ.get("I2RSI_MAX_IMAGE_EDGE", "1536")),
        )
