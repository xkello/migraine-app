import os
import sys
from pathlib import Path
import django

# Add project root (folder that contains manage.py) to PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "migraine_site.settings")
django.setup()

from tracker.ml.train_global import train_global_occurrence

if __name__ == "__main__":
    res = train_global_occurrence()
    print(res)
