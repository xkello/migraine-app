from __future__ import annotations
"""Model explanation helpers for UI-friendly risk factor summaries."""

from typing import Dict, Any
import numpy as np
import pandas as pd


# ------------------------------------------------------------------ #
# Random Forest explanation (feature importance)
# ------------------------------------------------------------------ #

def explain_rf_prediction(pipeline, X_row: pd.DataFrame, top_k: int = 5) -> Dict[str, Any]:
    """
    Return the top global feature importances from a fitted RF pipeline as an
    explanation proxy.  RF importances are non-negative, so only 'top_positive'
    is populated; 'top_negative' is always an empty list.

    The dict format is intentionally identical to explain_linear_prediction so
    that views.py can consume it without changes.
    """
    if not hasattr(pipeline, "named_steps"):
        return {"top_positive": [], "top_negative": [],
                "note": "Explanation unavailable for this model type."}

    preprocess = pipeline.named_steps.get("preprocess")
    model = pipeline.named_steps.get("model")

    if preprocess is None or model is None:
        return {"top_positive": [], "top_negative": [],
                "note": "Pipeline is missing expected steps."}

    if not hasattr(model, "feature_importances_"):
        return {"top_positive": [], "top_negative": [],
                "note": "Model has no feature importances."}

    feature_names = preprocess.get_feature_names_out()
    importances = model.feature_importances_

    sorted_idx = np.argsort(importances)[::-1]
    top_positive = [
        {"feature": str(feature_names[i]), "contribution": float(importances[i])}
        for i in sorted_idx[:top_k]
        if importances[i] > 0
    ]

    return {
        "top_positive": top_positive,
        "top_negative": [],   # RF importances are always non-negative
    }


# ------------------------------------------------------------------ #
# Legacy logistic regression explanation (kept for fallback)
# ------------------------------------------------------------------ #

def _unwrap_pipeline(model_obj):
    """
    If model_obj is a CalibratedClassifierCV, the trained base estimator
    (our Pipeline) is stored in calibrated_classifiers_[0].estimator.
    Otherwise, return the object as-is.

    Args:
        model_obj: Calibrated estimator or plain sklearn Pipeline.

    Returns:
        Pipeline-like estimator exposing `named_steps` when available.
    """
    if hasattr(model_obj, "calibrated_classifiers_") and model_obj.calibrated_classifiers_:
        return model_obj.calibrated_classifiers_[0].estimator
    return model_obj


def explain_linear_prediction(model_pipeline_or_calibrated, X_row: pd.DataFrame, top_k: int = 5) -> Dict[str, Any]:
    """
    Linear coefficient-based explanation for legacy logistic regression models.
    Kept so the fallback path in predict.py still works.
    """
    pipe = _unwrap_pipeline(model_pipeline_or_calibrated)

    if not hasattr(pipe, "named_steps"):
        return {"top_positive": [], "top_negative": [], "note": "Explanation unavailable for this model type."}

    preprocess = pipe.named_steps["preprocess"]
    clf = pipe.named_steps["model"]

    Xt = preprocess.transform(X_row)
    feature_names = preprocess.get_feature_names_out()

    if not hasattr(clf, "coef_"):
        return {"top_positive": [], "top_negative": [], "note": "Model has no linear coefficients."}

    coefs = clf.coef_.ravel()
    arr = Xt.toarray().ravel() if hasattr(Xt, "toarray") else np.ravel(Xt)
    contrib = arr * coefs

    idx_sorted = np.argsort(contrib)
    neg_idx = idx_sorted[:top_k]
    pos_idx = idx_sorted[-top_k:][::-1]

    def pack(idxs):
        return [
            {"feature": str(feature_names[i]), "contribution": float(contrib[i])}
            for i in idxs
            if abs(contrib[i]) > 1e-12
        ]

    return {
        "top_positive": pack(pos_idx),
        "top_negative": pack(neg_idx),
    }
