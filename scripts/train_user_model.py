"""Utility script to train legacy per-user occurrence models."""

import os
import sys
from pathlib import Path
import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "migraine_site.settings")
django.setup()

from tracker.ml.train_user import train_all_users

if __name__ == "__main__":
    # Run legacy user-model training and print per-user outcomes.
    res = train_all_users()
    print(res)
