from __future__ import annotations

from typing import Dict, Any, Optional

import numpy as np
from django.contrib.auth import get_user_model
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import brier_score_loss, log_loss

from .config import MLConfig
from .features import build_dataset
from .preprocess import make_preprocess
from .storage import get_model_paths, save_model


def should_train_user_model(y_occ, cfg: MLConfig) -> bool:
    n = len(y_occ)
    positives = int(y_occ.sum())
    return (n >= cfg.USER_MIN_DAYS) and (positives >= cfg.USER_MIN_POSITIVES)


def train_user_occurrence(user_id: int, cfg: MLConfig | None = None) -> Dict[str, Any]:
    cfg = cfg or MLConfig()
    data = build_dataset(user_id=user_id, cfg=cfg)
    if data.X.empty:
        return {"ok": False, "reason": "No data for user"}

    if not should_train_user_model(data.y_occ, cfg):
        return {
            "ok": False,
            "reason": "Not enough data to train user model",
            "n_days": int(len(data.y_occ)),
            "n_positives": int(data.y_occ.sum()),
        }

    # Simple time split
    n = len(data.X)
    cut = int(n * 0.8) if n >= 50 else max(1, int(n * 0.7))
    X_train, X_test = data.X.iloc[:cut], data.X.iloc[cut:]
    y_train, y_test = data.y_occ.iloc[:cut], data.y_occ.iloc[cut:]

    preprocess = make_preprocess(data.feature_columns)

    # Stronger regularization than global to reduce overfitting
    model = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=5e-4,       # stronger than global
        max_iter=3000,
        tol=1e-3,
        random_state=42,
    )

    pipe = Pipeline(steps=[
        ("preprocess", preprocess),
        ("model", model),
    ])

    pipe.fit(X_train, y_train)
    p_test = pipe.predict_proba(X_test)[:, 1]

    metrics = {
        "user_id": int(user_id),
        "n_samples": int(n),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "pos_rate_train": float(y_train.mean()),
        "pos_rate_test": float(y_test.mean()) if len(y_test) else None,
        "brier": float(brier_score_loss(y_test, p_test)) if len(y_test) else None,
        "logloss": float(log_loss(y_test, p_test, labels=[0, 1])) if len(y_test) else None,
        "feature_schema_version": cfg.FEATURE_SCHEMA_VERSION,
        "label_shift_days": cfg.LABEL_SHIFT_DAYS,
    }

    paths = get_model_paths()
    path = paths.user_occurrence(user_id)
    save_model({"pipeline": pipe, "metrics": metrics, "feature_columns": data.feature_columns}, path)
    return {"ok": True, "metrics": metrics, "path": str(path)}


def train_all_users(cfg: MLConfig | None = None) -> Dict[str, Any]:
    cfg = cfg or MLConfig()
    User = get_user_model()
    results = {"ok": True, "users": []}
    for u in User.objects.all().only("id"):
        res = train_user_occurrence(u.id, cfg=cfg)
        results["users"].append(res)
    return results
