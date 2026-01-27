from __future__ import annotations

from typing import Dict, Any
import numpy as np
import pandas as pd


def _unwrap_pipeline(model_obj):
    """
    If model_obj is a CalibratedClassifierCV, the trained base estimator
    (our Pipeline) is stored in calibrated_classifiers_[0].estimator.
    Otherwise, return the object as-is.
    """
    # CalibratedClassifierCV exposes calibrated_classifiers_ after fitting
    if hasattr(model_obj, "calibrated_classifiers_") and model_obj.calibrated_classifiers_:
        # Each entry has .estimator (your original pipeline)
        return model_obj.calibrated_classifiers_[0].estimator
    return model_obj


def explain_linear_prediction(model_pipeline_or_calibrated, X_row: pd.DataFrame, top_k: int = 5) -> Dict[str, Any]:
    """
    Works for:
      - Pipeline(preprocess -> linear model)
      - CalibratedClassifierCV wrapping that Pipeline
    Returns top positive/negative contributions in transformed space.
    """
    pipe = _unwrap_pipeline(model_pipeline_or_calibrated)

    if not hasattr(pipe, "named_steps"):
        return {"top_positive": [], "top_negative": [], "note": "Explanation unavailable for this model type."}

    preprocess = pipe.named_steps["preprocess"]
    clf = pipe.named_steps["model"]

    Xt = preprocess.transform(X_row)
    feature_names = preprocess.get_feature_names_out()

    # SGDClassifier has coef_
    if not hasattr(clf, "coef_"):
        return {"top_positive": [], "top_negative": [], "note": "Model has no linear coefficients."}

    coefs = clf.coef_.ravel()

    # contribution = x * w (in transformed space)
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
