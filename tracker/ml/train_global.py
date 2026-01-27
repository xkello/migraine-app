from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, Tuple

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss, mean_absolute_error
from sklearn.calibration import CalibratedClassifierCV

from .config import MLConfig
from .features import build_dataset
from .preprocess import make_preprocess
from .storage import get_model_paths, save_model


#def _time_split(X, y, test_fraction: float = 0.2):
#    n = len(X)
#    if n < 50:
#        return X, X, y, y  # tiny; evaluate on train (still log metrics)
#    cut = int(n * (1 - test_fraction))
#    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]
def _time_split(X, y, test_fraction: float = 0.3):
    n = len(X)
    if n < 5:
        return X, X, y, y
    cut = max(1, int(n * (1 - test_fraction)))
    if cut >= n:
        cut = n - 1
    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]



def train_global_occurrence(cfg: MLConfig | None = None) -> Dict[str, Any]:
    cfg = cfg or MLConfig()
    data = build_dataset(user_id=None, cfg=cfg)
    if data.X.empty:
        return {"ok": False, "reason": "No data"}

    X_train, X_test, y_train, y_test = _time_split(data.X, data.y_occ)

    preprocess = make_preprocess(data.feature_columns)
    model = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=5e-2,  # stronger regularization
        max_iter=5000,
        tol=1e-3,
        random_state=42,
        class_weight="balanced",
    )

    pipe = Pipeline(steps=[
        ("preprocess", preprocess),
        ("model", model),
    ])

    pipe.fit(X_train, y_train)

    calibrated = CalibratedClassifierCV(pipe, method="sigmoid", cv=2)
    calibrated.fit(X_train, y_train)

    # Probabilities
    p_test = calibrated.predict_proba(X_test)[:, 1]
    p_train = calibrated.predict_proba(X_train)[:, 1]

    metrics = {
        "n_samples": int(len(data.X)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "pos_rate_train": float(y_train.mean()),
        "pos_rate_test": float(y_test.mean()),
        "auc": float(roc_auc_score(y_test, p_test)) if len(np.unique(y_test)) > 1 else None,
        "auprc": float(average_precision_score(y_test, p_test)) if len(np.unique(y_test)) > 1 else None,
        "brier": float(brier_score_loss(y_test, p_test)),
        "logloss": float(log_loss(y_test, p_test, labels=[0, 1])),
        "feature_schema_version": cfg.FEATURE_SCHEMA_VERSION,
        "label_shift_days": cfg.LABEL_SHIFT_DAYS,
    }

    paths = get_model_paths()
    save_model({"pipeline": calibrated, "metrics": metrics, "feature_columns": data.feature_columns}, paths.global_occurrence)
    return {"ok": True, "metrics": metrics, "path": str(paths.global_occurrence)}


def train_global_severity(cfg: MLConfig | None = None) -> Dict[str, Any]:
    """
    Optional v2: train severity regressor on migraine days only.
    """
    cfg = cfg or MLConfig()
    data = build_dataset(user_id=None, cfg=cfg)
    if data.X_migraine_days.empty:
        return {"ok": False, "reason": "No migraine-day severity data"}

    X_train, X_test, y_train, y_test = _time_split(data.X_migraine_days, data.y_intensity)

    preprocess = make_preprocess(data.feature_columns)
    model = SGDRegressor(
        loss="huber",
        penalty="l2",
        alpha=1e-4,
        max_iter=2000,
        tol=1e-3,
        random_state=42,
    )

    pipe = Pipeline(steps=[
        ("preprocess", preprocess),
        ("model", model),
    ])

    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)

    metrics = {
        "n_samples": int(len(data.X_migraine_days)),
        "mae_intensity": float(mean_absolute_error(y_test, pred)),
        "feature_schema_version": cfg.FEATURE_SCHEMA_VERSION,
        "label_shift_days": cfg.LABEL_SHIFT_DAYS,
    }

    paths = get_model_paths()
    save_model({"pipeline": pipe, "metrics": metrics, "feature_columns": data.feature_columns}, paths.global_severity)
    return {"ok": True, "metrics": metrics, "path": str(paths.global_severity)}
