from __future__ import annotations

from typing import List, Tuple

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def make_preprocess(feature_columns: List[str]) -> ColumnTransformer:
    """
    Everything is numeric/boolean except a few discrete time features.
    We'll treat weekday/month as categorical (one-hot) and scale numeric columns.
    """
    categorical = [c for c in feature_columns if c in ("weekday", "month")]
    numeric = [c for c in feature_columns if c not in categorical]

    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric),
            ("cat", cat_pipe, categorical),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
