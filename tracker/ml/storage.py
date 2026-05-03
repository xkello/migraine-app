from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
from django.conf import settings


@dataclass(frozen=True)
class ModelPaths:
    base: Path

    # ------------------------------------------------------------------ #
    # Random Forest (production model)
    # ------------------------------------------------------------------ #
    @property
    def random_forest(self) -> Path:
        return self.base / "random_forest" / "latest.joblib"

    @property
    def random_forest_metadata(self) -> Path:
        return self.base / "random_forest" / "metadata.json"

    @property
    def random_forest_feature_importance(self) -> Path:
        return self.base / "random_forest" / "feature_importance.json"

    def random_forest_archive(self, timestamp: str) -> Path:
        return self.base / "archive" / f"random_forest_{timestamp}.joblib"

    # ------------------------------------------------------------------ #
    # Legacy logistic regression paths (kept for rollback)
    # ------------------------------------------------------------------ #
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
        base_dir = getattr(settings, "BASE_DIR", None)
        if base_dir is None:
            raise RuntimeError("Neither ML_MODELS_DIR nor BASE_DIR is set in Django settings")
        base = Path(base_dir) / "models"
    return ModelPaths(base=Path(base))


def save_model(obj: Any, path: Path) -> None:
    get_model_paths().ensure_parent(path)
    joblib.dump(obj, path)


def load_model(path: Path) -> Any:
    return joblib.load(path)


def save_json(obj: Any, path: Path) -> None:
    get_model_paths().ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def model_exists(path: Path) -> bool:
    return path.exists() and path.is_file()
