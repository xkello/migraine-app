from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model

from tracker.models import DailyLog
from .config import MLConfig


RAW_NUMERIC_COLS = [
    "sleep_hours",
    "physical_activity_minutes",
    "physical_activity_difficulty",
    "stress_level",
    "caffeine_mg",
    "heavy_meals",
    "hydration_liters",
    "alcohol_consumption",
    "weather_temp_c",
    "weather_humidity",
    "weather_pressure_hpa",
]

RAW_BOOL_COLS = [
    "menstruation",
]

TARGET_COL_OCC = "had_migraine"
TARGET_COL_INT = "migraine_intensity"
TARGET_COL_DUR = "migraine_duration_hours"


@dataclass
class BuiltDataset:
    X: pd.DataFrame
    y_occ: pd.Series
    # for v2
    X_migraine_days: pd.DataFrame
    y_intensity: pd.Series
    y_duration: pd.Series
    feature_columns: List[str]


def _query_logs(user_id: Optional[int] = None) -> pd.DataFrame:
    qs = DailyLog.objects.all().values(
        "user_id",
        "date",
        *RAW_NUMERIC_COLS,
        *RAW_BOOL_COLS,
        "meds_taken",
        TARGET_COL_OCC,
        TARGET_COL_INT,
        TARGET_COL_DUR,
    )
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    df = pd.DataFrame.from_records(qs)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["user_id", "date"]).reset_index(drop=True)

    # meds simple v1 feature: any meds string present
    #df["meds_any"] = df["meds_taken"].fillna("").astype(str).str.strip().ne("").astype(int)

    # time features
    df["weekday"] = df["date"].dt.weekday.astype(int)
    df["month"] = df["date"].dt.month.astype(int)

    return df


def _add_group_lags_and_rolls(df: pd.DataFrame, cfg: MLConfig) -> pd.DataFrame:
    g = df.groupby("user_id", sort=False)

    # lag migraine + lag of some key predictors
    for col in [
        TARGET_COL_OCC,
        "sleep_hours",
        "stress_level",
        "caffeine_mg",
        "hydration_liters",
        "alcohol_consumption",
        "weather_pressure_hpa",
        "weather_temp_c",
        "weather_humidity",
    ]:
        df[f"{col}_lag1"] = g[col].shift(1)

    # deltas (today - yesterday)
    for col in ["weather_pressure_hpa", "weather_temp_c", "weather_humidity"]:
        df[f"{col}_delta1"] = df[col] - df[f"{col}_lag1"]

    # rolling features (previous days only -> shift(1) before rolling to avoid leakage)
    for w in cfg.ROLL_WINDOWS:
        for col in ["sleep_hours", "stress_level", "caffeine_mg", "hydration_liters", "alcohol_consumption", "heavy_meals"]:
            df[f"{col}_roll_mean_{w}"] = g[col].shift(1).rolling(w, min_periods=1).mean().reset_index(level=0, drop=True)

        # migraine count in last w days (excluding today)
        df[f"migraine_roll_sum_{w}"] = g[TARGET_COL_OCC].shift(1).rolling(w, min_periods=1).sum().reset_index(level=0, drop=True)

    return df


def build_dataset(user_id: Optional[int] = None, cfg: Optional[MLConfig] = None) -> BuiltDataset:
    cfg = cfg or MLConfig()
    df = _query_logs(user_id=user_id)
    if df.empty:
        return BuiltDataset(
            X=pd.DataFrame(),
            y_occ=pd.Series(dtype=int),
            X_migraine_days=pd.DataFrame(),
            y_intensity=pd.Series(dtype=float),
            y_duration=pd.Series(dtype=float),
            feature_columns=[],
        )

    df = _add_group_lags_and_rolls(df, cfg)

    # Create label for future day if shift > 0:
    # y(t) = had_migraine(t + shift), features from day t
    g = df.groupby("user_id", sort=False)
    if cfg.LABEL_SHIFT_DAYS > 0:
        df["y_occ"] = g[TARGET_COL_OCC].shift(-cfg.LABEL_SHIFT_DAYS)
        df["y_int"] = g[TARGET_COL_INT].shift(-cfg.LABEL_SHIFT_DAYS)
        df["y_dur"] = g[TARGET_COL_DUR].shift(-cfg.LABEL_SHIFT_DAYS)
    else:
        df["y_occ"] = df[TARGET_COL_OCC]
        df["y_int"] = df[TARGET_COL_INT]
        df["y_dur"] = df[TARGET_COL_DUR]

    # Drop rows where y is unknown due to shifting
    df = df.dropna(subset=["y_occ"]).copy()
    df["y_occ"] = df["y_occ"].astype(int)

    # Define feature columns (exclude non-features / targets / ids)
    drop_cols = {
        "user_id",
        "date",
        "meds_taken",
        TARGET_COL_OCC,
        TARGET_COL_INT,
        TARGET_COL_DUR,
        "y_occ",
        "y_int",
        "y_dur",
    }
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols].copy()
    y_occ = df["y_occ"].copy()

    # Severity dataset: only where migraine actually occurred (y_occ==1) and intensity/duration present
    migraine_mask = (df["y_occ"] == 1) & df["y_int"].notna() & df["y_dur"].notna()
    X_m = df.loc[migraine_mask, feature_cols].copy()
    y_int = df.loc[migraine_mask, "y_int"].astype(float).copy()
    y_dur = df.loc[migraine_mask, "y_dur"].astype(float).copy()

    return BuiltDataset(
        X=X,
        y_occ=y_occ,
        X_migraine_days=X_m,
        y_intensity=y_int,
        y_duration=y_dur,
        feature_columns=feature_cols,
    )
