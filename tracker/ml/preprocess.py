from __future__ import annotations

from typing import List

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# Columns that must be treated as categorical and one-hot encoded.
# Must match what features.py produces.
CATEGORICAL_FEATURE_NAMES = {
    "weekday",              # "Mon" … "Sun"
    "month",                # "Jan" … "Dec"
    "weekend",              # "yes" / "no"
    "weather_description",  # free-text category from OpenWeather
    "menstruation",         # "yes" / "no"
}


def make_preprocess(feature_columns: List[str]) -> ColumnTransformer:
    """
    Preprocessing pipeline for the Random Forest classifier.

    - Categorical columns: mode imputation + one-hot encoding
      (handle_unknown="ignore" so unseen categories at inference do not crash)
    - Numeric / boolean columns: median imputation
      (scaling is intentionally omitted — not required for Random Forest)
    """
    categorical = [c for c in feature_columns if c in CATEGORICAL_FEATURE_NAMES]
    numeric = [c for c in feature_columns if c not in CATEGORICAL_FEATURE_NAMES]

    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        # No StandardScaler — not needed for tree-based models
    ])

    cat_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric),
            ("cat", cat_pipe, categorical),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
