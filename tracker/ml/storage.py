from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import joblib
from django.conf import settings


@dataclass(frozen=True)
class ModelPaths:
    base: Path

    @property
    def global_occurrence(self) -> Path:
        return self.base / "global" / "occurrence" / "latest.joblib"

    @property
    def global_severity(self) -> Path:
        return self.base / "global" / "severity" / "latest.joblib"

    def user_occurrence(self, user_id: int) -> Path:
        return self.base / "users" / str(user_id) / "occurrence" / "latest.joblib"

    def ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)


def get_model_paths() -> ModelPaths:
    base = getattr(settings, "ML_MODELS_DIR", None)
    if base is None:
        raise RuntimeError("ML_MODELS_DIR is not set in settings.py")
    return ModelPaths(base=Path(base))


def save_model(obj: Any, path: Path) -> None:
    get_model_paths().ensure_parent(path)
    joblib.dump(obj, path)


def load_model(path: Path) -> Any:
    return joblib.load(path)


def model_exists(path: Path) -> bool:
    return path.exists() and path.is_file()
