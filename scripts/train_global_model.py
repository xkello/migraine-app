#!/usr/bin/env python
"""
scripts/train_global_model.py
──────────────────────────────
Daily cron script that retrains the Random Forest migraine-risk model.

Intended schedule (crontab example):
    0 2 * * * /path/to/venv/bin/python /path/to/scripts/train_global_model.py \
              >> /var/log/migraine_ml_train.log 2>&1

Safety guarantees:
 - The existing model artifact is NOT overwritten unless the new candidate
   passes all data-quality guards AND a post-training sanity check.
 - If training fails the old model stays active and the web app is unaffected.
 - A timestamped archive of the previous model is kept before overwriting.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap Django ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "migraine_site.settings")

import django
django.setup()
# ─────────────────────────────────────────────────────────────────────────────

from tracker.ml.train_global import train_rf_occurrence
from tracker.ml.config import MLConfig
from tracker.ml.predict import clear_model_cache

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("cron.train_global_model")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    """Execute one offline RF retraining run and return process exit code."""
    start = datetime.now(tz=timezone.utc)
    logger.info("=" * 60)
    logger.info("Migraine RF model — daily retraining job")
    logger.info("Start time: %s", start.isoformat())
    logger.info("=" * 60)

    cfg = MLConfig()
    logger.info("Configuration: trees=%d  min_leaf=%d  threshold=%.2f  min_records=%d  schema=%s",
                cfg.RF_N_ESTIMATORS, cfg.RF_MIN_SAMPLES_LEAF,
                cfg.RF_THRESHOLD, cfg.RF_MIN_TRAINING_RECORDS,
                cfg.FEATURE_SCHEMA_VERSION)

    # ---- Run training ------------------------------------------------ #
    result = train_rf_occurrence(cfg=cfg)

    # ---- Report results ---------------------------------------------- #
    end = datetime.now(tz=timezone.utc)
    elapsed = (end - start).total_seconds()

    if result.get("ok"):
        metrics = result.get("metrics", {})
        logger.info("-" * 60)
        logger.info("Training SUCCEEDED in %.1f s", elapsed)
        logger.info("Model saved  → %s", result.get("path"))
        logger.info("Records      : total=%d  pos=%d  neg=%d",
                    metrics.get("n_samples", 0),
                    metrics.get("n_positive", 0),
                    metrics.get("n_negative", 0))
        logger.info("Class rates  : train_pos=%.3f  test_pos=%.3f",
                    metrics.get("pos_rate_train", 0.0),
                    metrics.get("pos_rate_test", 0.0))
        logger.info("Eval metrics : AUC=%-6s  Brier=%.4f  LogLoss=%.4f",
                    f"{metrics['auc']:.3f}" if metrics.get("auc") is not None else "N/A",
                    metrics.get("brier", 0.0),
                    metrics.get("logloss", 0.0))
        logger.info("Features     : %d post-preprocessing columns", result.get("n_features", 0))

        top = result.get("top_features", [])
        if top:
            logger.info("Top features :")
            for entry in top[:10]:
                logger.info("  #%2d  %-40s  %.5f",
                            entry["rank"], entry["feature"], entry["importance"])

        # Invalidate in-process model cache so next request picks up new model
        clear_model_cache()
        logger.info("In-process model cache cleared")
        logger.info("=" * 60)
        return 0

    else:
        reason = result.get("reason", "unknown error")
        logger.error("-" * 60)
        logger.error("Training FAILED in %.1f s", elapsed)
        logger.error("Reason: %s", reason)
        logger.error("The previous model artifact was NOT overwritten.")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
