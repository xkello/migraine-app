from dataclasses import dataclass


@dataclass(frozen=True)
class MLConfig:
    # Predict migraine for the NEXT day using today's log
    LABEL_SHIFT_DAYS: int = 1

    # Rolling windows
    ROLL_WINDOWS: tuple[int, ...] = (3, 7)

    # User model thresholds (kept for backward compat; user models are no longer used in prediction)
    USER_MIN_DAYS: int = 30
    USER_MIN_POSITIVES: int = 5
    USER_RETRAIN_NEW_LOGS: int = 10

    # Blending (kept for backward compat; blending is disabled)
    BLEND_N0: int = 120

    # Global retrain suggestion (trigger via cron)
    GLOBAL_MIN_NEW_LOGS: int = 100

    # Feature set versioning — bump this when feature engineering changes
    FEATURE_SCHEMA_VERSION: str = "v2"

    # ------------------------------------------------------------------ #
    # Random Forest production configuration
    # ------------------------------------------------------------------ #
    RF_N_ESTIMATORS: int = 500
    RF_MIN_SAMPLES_LEAF: int = 5
    RF_RANDOM_STATE: int = 42
    # max_features uses sklearn default "sqrt" — set as None here, resolved in train
    RF_MAX_FEATURES: str = "sqrt"

    # Classification threshold — 0.35 increases sensitivity for preventive use
    RF_THRESHOLD: float = 0.35

    # Minimum labeled records required before overwriting the saved model
    RF_MIN_TRAINING_RECORDS: int = 100
