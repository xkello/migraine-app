from __future__ import annotations

from functools import lru_cache
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from .config import MLConfig
from .features import build_dataset
from .storage import get_model_paths, load_model, model_exists
from .explain import explain_linear_prediction


def blend_weight(n_user_days: int, cfg: MLConfig) -> float:
    # Smoothly increases with n; capped [0, 1]
    w = n_user_days / (n_user_days + cfg.BLEND_N0)
    return float(max(0.0, min(1.0, w)))


@lru_cache(maxsize=4)
def _load_global_occurrence():
    paths = get_model_paths()
    if not model_exists(paths.global_occurrence):
        return None
    return load_model(paths.global_occurrence)


@lru_cache(maxsize=128)
def _load_user_occurrence(user_id: int):
    paths = get_model_paths()
    p = paths.user_occurrence(user_id)
    if not model_exists(p):
        return None
    return load_model(p)


def predict_next_day_risk(user_id: int, cfg: MLConfig | None = None, with_explain: bool = True) -> Dict[str, Any]:
    """
    Predict migraine risk for the next day based on the user's latest available log.
    Because LABEL_SHIFT_DAYS=1, we use the latest row of X to predict tomorrow.
    """
    cfg = cfg or MLConfig()
    global_obj = _load_global_occurrence()
    if global_obj is None:
        return {"ok": False, "reason": "Global model not trained yet"}

    # Build dataset for user, take last feature row
    data = build_dataset(user_id=user_id, cfg=cfg)
    if data.X.empty:
        return {"ok": False, "reason": "No logs for user"}

    X_last = data.X.tail(1)
    global_pipe = global_obj["pipeline"]
    p_global = float(global_pipe.predict_proba(X_last)[:, 1][0])
    p_global = float(np.clip(p_global, 1e-4, 1 - 1e-4))

    # optional user model
    user_obj = _load_user_occurrence(user_id)
    if user_obj is None:
        expl = explain_linear_prediction(global_pipe, X_last) if with_explain else None
        return {
            "ok": True,
            "p_global": p_global,
            "p_user": None,
            "p_final": p_global,
            "blend_weight": 0.0,
            "explain": expl,
            "used": "global_only",
        }

    user_pipe = user_obj["pipeline"]
    p_user = float(user_pipe.predict_proba(X_last)[:, 1][0])
    p_user = float(np.clip(p_user, 1e-4, 1 - 1e-4))

    w = blend_weight(n_user_days=len(data.X), cfg=cfg)
    p_final = float(w * p_user + (1 - w) * p_global)

    expl = explain_linear_prediction(user_pipe, X_last) if with_explain else None
    return {
        "ok": True,
        "p_global": p_global,
        "p_user": p_user,
        "p_final": p_final,
        "blend_weight": w,
        "explain": expl,
        "used": "blended",
    }
