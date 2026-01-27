from dataclasses import dataclass


@dataclass(frozen=True)
class MLConfig:
    # Predict migraine for the NEXT day using today's log
    LABEL_SHIFT_DAYS: int = 1

    # Rolling windows
    ROLL_WINDOWS: tuple[int, ...] = (3, 7)

    # User model thresholds (avoid training on tiny noisy history)
    USER_MIN_DAYS: int = 30
    USER_MIN_POSITIVES: int = 5
    USER_RETRAIN_NEW_LOGS: int = 10

    # Blending: trust user model more with more data
    BLEND_N0: int = 120  # higher -> slower trust in user model

    # Global retrain suggestion (trigger via cron)
    GLOBAL_MIN_NEW_LOGS: int = 100

    # Feature set versioning (bump when change feature engineering)
    FEATURE_SCHEMA_VERSION: str = "v1"
