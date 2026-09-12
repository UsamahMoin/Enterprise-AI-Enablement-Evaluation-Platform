"""Filesystem locations resolved once, so callers do not count `parents[n]`.

Locally the layout is <repo>/backend/app and <repo>/seed. In the container the
application lives at /app and the seed data is copied to /seed, so the same
"one level above the backend directory" rule holds in both.
"""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
SEED_DIR = REPO_ROOT / "seed"
