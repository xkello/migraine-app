from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from typing import Dict, Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    log_loss, mean_absolute_error,
)
from sklearn.pipeline import Pipeline

from .config import MLConfig
from .features import build_dataset
from .preprocess import make_preprocess
from .storage import get_model_paths, save_model, save_json, model_exists

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _time_split(X, y, test_fraction: float = 0.3):
    n = len(X)
    if n < 5:
        return X, X, y, y
    cut = max(1, int(n * (1 - test_fraction)))
    if cut >= n:
        cut = n - 1
    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]


# ------------------------------------------------------------------ #
# Random Forest occurrence model  (production model)
# ------------------------------------------------------------------ #

def train_rf_occurrence(cfg: MLConfig | None = None) -> Dict[str, Any]:
    """
    Train a Random Forest classifier to predict next-day migraine occurrence.

    This function is designed to be called offline (nightly cron).
    It will NOT overwrite the existing model artifact when safety guards fail.
    """
    cfg = cfg or MLConfig()
    trained_at = datetime.now(tz=timezone.utc).isoformat()

    logger.info("RF training started at %s", trained_at)

    # ---- 1. Load data ------------------------------------------------ #
    data = build_dataset(user_id=None, cfg=cfg)
    if data.X.empty:
        logger.error("RF training aborted: no data found")
        return {"ok": False, "reason": "No data"}

    n_total = len(data.X)
    n_pos = int(data.y_occ.sum())
    n_neg = n_total - n_pos

    logger.info("Dataset: %d total | %d positive | %d negative", n_total, n_pos, n_neg)

    # ---- 2. Minimum data guards -------------------------------------- #
    if n_total < cfg.RF_MIN_TRAINING_RECORDS:
        reason = f"Insufficient data: {n_total} records < minimum {cfg.RF_MIN_TRAINING_RECORDS}"
        logger.warning("RF training aborted: %s", reason)
        return {"ok": False, "reason": reason}

    if n_pos == 0 or n_neg == 0:
        reason = f"Only one class present (pos={n_pos}, neg={n_neg})"
        logger.warning("RF training aborted: %s", reason)
        return {"ok": False, "reason": reason}

    # ---- 3. Time-based split ----------------------------------------- #
    X_train, X_test, y_train, y_test = _time_split(data.X, data.y_occ)
    logger.info("Split → train=%d test=%d", len(X_train), len(X_test))

    # ---- 4. Build pipeline ------------------------------------------- #
    preprocess = make_preprocess(data.feature_columns)

    model = RandomForestClassifier(
        n_estimators=cfg.RF_N_ESTIMATORS,
        max_features=cfg.RF_MAX_FEATURES,
        min_samples_leaf=cfg.RF_MIN_SAMPLES_LEAF,
        random_state=cfg.RF_RANDOM_STATE,
        class_weight=None,   # change to "balanced" if class imbalance becomes a problem
        n_jobs=-1,
    )

    pipe = Pipeline(steps=[
        ("preprocess", preprocess),
        ("model", model),
    ])

    # ---- 5. Fit ------------------------------------------------------ #
    try:
        pipe.fit(X_train, y_train)
    except Exception as exc:
        logger.exception("RF pipeline fit failed: %s", exc)
        return {"ok": False, "reason": f"Training failed: {exc}"}

    # ---- 6. Evaluate ------------------------------------------------- #
    p_test = pipe.predict_proba(X_test)[:, 1]
    has_both_classes_test = len(np.unique(y_test)) > 1

    metrics: Dict[str, Any] = {
        "n_samples": n_total,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "pos_rate_train": float(y_train.mean()),
        "pos_rate_test": float(y_test.mean()),
        "auc": float(roc_auc_score(y_test, p_test)) if has_both_classes_test else None,
        "auprc": float(average_precision_score(y_test, p_test)) if has_both_classes_test else None,
        "brier": float(brier_score_loss(y_test, p_test)),
        "logloss": float(log_loss(y_test, p_test, labels=[0, 1])),
        "feature_schema_version": cfg.FEATURE_SCHEMA_VERSION,
        "label_shift_days": cfg.LABEL_SHIFT_DAYS,
        "threshold": cfg.RF_THRESHOLD,
    }
    logger.info("Eval metrics: AUC=%.3f  Brier=%.4f  LogLoss=%.4f",
                metrics["auc"] or 0.0, metrics["brier"], metrics["logloss"])

    # ---- 7. Feature importance --------------------------------------- #
    feature_names = pipe.named_steps["preprocess"].get_feature_names_out()
    importances = pipe.named_steps["model"].feature_importances_
    importance_list = [
        {"rank": i + 1, "feature": str(fn), "importance": round(float(imp), 6)}
        for i, (fn, imp) in enumerate(
            sorted(zip(feature_names, importances), key=lambda x: -x[1])
        )
    ]
    logger.info("Top-5 features: %s",
                [(e["feature"], e["importance"]) for e in importance_list[:5]])

    # ---- 8. Sanity check before saving ------------------------------- #
    try:
        sample_X = data.X.tail(min(5, len(data.X)))
        sample_probs = pipe.predict_proba(sample_X)[:, 1]
        if not all(0.0 <= float(p) <= 1.0 for p in sample_probs):
            raise ValueError("Probability out of [0, 1] range")
        # Check unknown category handling: should not raise
        pipe.predict_proba(sample_X)
        logger.info("Sanity check passed (probs: %s)", [round(float(p), 3) for p in sample_probs])
    except Exception as exc:
        logger.exception("Post-training sanity check failed: %s", exc)
        return {"ok": False, "reason": f"Sanity check failed: {exc}"}

    # ---- 9. Archive previous model if it exists ---------------------- #
    paths = get_model_paths()
    if model_exists(paths.random_forest):
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = paths.random_forest_archive(ts)
        paths.ensure_parent(archive_path)
        shutil.copy2(paths.random_forest, archive_path)
        logger.info("Previous model archived to %s", archive_path)

    # ---- 10. Save model artifact ------------------------------------- #
    artifact = {
        "pipeline": pipe,
        "metrics": metrics,
        "feature_columns": data.feature_columns,
        "threshold": cfg.RF_THRESHOLD,
        "model_type": "RandomForestClassifier",
        "model_version": cfg.FEATURE_SCHEMA_VERSION,
    }
    save_model(artifact, paths.random_forest)
    logger.info("Model saved → %s", paths.random_forest)

    # ---- 11. Save metadata ------------------------------------------- #
    metadata = {
        "model_type": "RandomForestClassifier",
        "model_version": cfg.FEATURE_SCHEMA_VERSION,
        "trained_at": trained_at,
        "threshold": cfg.RF_THRESHOLD,
        "target": "had_migraine",
        "positive_class": "yes / 1",
        "training_record_count": n_total,
        "positive_class_count": n_pos,
        "negative_class_count": n_neg,
        "numeric_features": [c for c in data.feature_columns if c not in ("weekday", "month", "weekend", "weather_description", "menstruation")],
        "categorical_features": ["weekday", "month", "weekend", "weather_description", "menstruation"],
        "excluded_features": ["date", "user_id", "had_migraine", "migraine_intensity", "migraine_duration_hours"],
        "preprocessing_description": "median imputation for numeric; mode imputation + one-hot encoding for categorical; no scaling",
        "rf_n_estimators": cfg.RF_N_ESTIMATORS,
        "rf_min_samples_leaf": cfg.RF_MIN_SAMPLES_LEAF,
        "rf_max_features": cfg.RF_MAX_FEATURES,
        "rf_random_state": cfg.RF_RANDOM_STATE,
        "metrics": metrics,
        "feature_importance_path": str(paths.random_forest_feature_importance),
    }
    save_json(metadata, paths.random_forest_metadata)

    # ---- 12. Save feature importance --------------------------------- #
    save_json(importance_list, paths.random_forest_feature_importance)
    logger.info("Feature importance saved → %s", paths.random_forest_feature_importance)

    logger.info("RF training completed successfully at %s", datetime.now(tz=timezone.utc).isoformat())

    return {
        "ok": True,
        "metrics": metrics,
        "path": str(paths.random_forest),
        "n_features": len(feature_names),
        "top_features": importance_list[:10],
    }


# ------------------------------------------------------------------ #
# Backward-compatible alias so existing management commands still work
# ------------------------------------------------------------------ #

def train_global_occurrence(cfg: MLConfig | None = None) -> Dict[str, Any]:
    """Alias for train_rf_occurrence — kept so existing management commands work."""
    return train_rf_occurrence(cfg=cfg)


# ------------------------------------------------------------------ #
# Severity regressor (unchanged, used optionally)
# ------------------------------------------------------------------ #

def train_global_severity(cfg: MLConfig | None = None) -> Dict[str, Any]:
    """Optional: train a severity regressor on migraine days only."""
    from sklearn.linear_model import SGDRegressor

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
