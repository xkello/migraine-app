from __future__ import annotations
"""Runtime prediction entrypoints for migraine risk estimation.

The production request flow loads a previously trained model artifact and
performs inference only; no tuning or retraining is done in requests.
"""

from functools import lru_cache
from typing import Dict, Any, Optional, Tuple

import numpy as np

from .config import MLConfig
from .features import build_dataset
from .storage import get_model_paths, load_model, model_exists
from .explain import explain_rf_prediction, explain_linear_prediction


# ------------------------------------------------------------------ #
# Model loading (cached per process; restart or call clear_model_cache()
# after the cron script replaces the model artifact)
# ------------------------------------------------------------------ #

@lru_cache(maxsize=1)
def _load_rf_model() -> Tuple[Optional[Dict], str]:
    """
    Load the best available model artifact.

    Priority:
      1. Random Forest (production model)   → models/random_forest/latest.joblib
      2. Legacy logistic regression model   → models/global/occurrence/latest.joblib

    Returns (artifact_dict, model_type_str) or (None, "none").
    """
    paths = get_model_paths()

    if model_exists(paths.random_forest):
        obj = load_model(paths.random_forest)
        return obj, "random_forest"

    # Graceful fallback to old LR model so the app keeps working while the
    # first RF training has not run yet.
    if model_exists(paths.global_occurrence):
        obj = load_model(paths.global_occurrence)
        return obj, "logistic_regression"

    return None, "none"


def clear_model_cache() -> None:
    """Invalidate the in-process model cache (call after cron retraining)."""
    _load_rf_model.cache_clear()


# ------------------------------------------------------------------ #
# Public prediction interface
# ------------------------------------------------------------------ #

def predict_next_day_risk(
    user_id: int,
    cfg: MLConfig | None = None,
    with_explain: bool = True,
) -> Dict[str, Any]:
    """
    Predict migraine risk for the next day based on the user's latest log.

    Args:
        user_id: ID of the authenticated user.
        cfg: Optional MLConfig override.
        with_explain: Include model explanation payload when True.

    Returns:
        Dict[str, Any]: Prediction payload.

    Payload keys (all present regardless of model type):
        ok              – bool: False if prediction could not be made
        reason          – str: why prediction failed (only when ok=False)
        p_final         – float: probability of migraine [0, 1]  (backward-compat alias)
        p_global        – float: same as p_final
        p_user          – None  (user-specific models disabled in RF era)
        probability     – float: same as p_final
        threshold       – float: classification threshold (0.35)
        predicted_class – "yes" / "no"
        risk_label      – "lower risk" / "increased risk" / "high risk"
        model_type      – "Random Forest" / "Logistic Regression"
        model_version   – str
        blend_weight    – 0.0  (blending disabled)
        explain         – dict with top_positive / top_negative feature lists
        used            – "random_forest" / "logistic_regression_fallback"
    """
    cfg = cfg or MLConfig()

    model_obj, model_type = _load_rf_model()
    if model_obj is None:
        return {"ok": False, "reason": "No trained model available. Run the daily training cron."}

    # Build feature dataset for this user
    data = build_dataset(user_id=user_id, cfg=cfg)
    if data.X.empty:
        return {"ok": False, "reason": "No logs for user"}

    X_last = data.X.tail(1)
    pipe = model_obj["pipeline"]

    # Threshold: prefer what was baked into the artifact; fall back to config
    threshold = float(model_obj.get("threshold", cfg.RF_THRESHOLD))

    # Predict probability of the positive class (migraine = 1)
    p = float(pipe.predict_proba(X_last)[:, 1][0])
    p = float(np.clip(p, 1e-4, 1 - 1e-4))

    # Apply threshold
    predicted_class = "yes" if p >= threshold else "no"

    # Risk label
    if p >= 0.60:
        risk_label_val = "high risk"
    elif p >= threshold:
        risk_label_val = "increased risk"
    else:
        risk_label_val = "lower risk"

    # Explanation
    expl: Optional[Dict] = None
    if with_explain:
        if model_type == "random_forest":
            expl = explain_rf_prediction(pipe, X_last)
        else:
            expl = explain_linear_prediction(pipe, X_last)

    model_version = model_obj.get(
        "model_version",
        model_obj.get("metrics", {}).get("feature_schema_version", "unknown"),
    )

    return {
        "ok": True,
        # Backward-compatible keys consumed by views.py
        "p_global": p,
        "p_user": None,
        "p_final": p,
        "blend_weight": 0.0,
        "explain": expl,
        "used": model_type,
        # New structured keys
        "probability": p,
        "threshold": threshold,
        "predicted_class": predicted_class,
        "risk_label": risk_label_val,
        "model_type": "Random Forest" if model_type == "random_forest" else "Logistic Regression",
        "model_version": model_version,
    }
