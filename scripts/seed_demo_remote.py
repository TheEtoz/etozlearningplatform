"""Seed demo content on a remote DB (Neon). Refuses when ETOZ_ENV=production
unless ETOZ_SEED_DEMO=1.

Usage:
  $env:DATABASE_URL = "…"
  $env:ETOZ_SEED_DEMO = "1"
  python scripts/seed_demo_remote.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env")
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1
    os.environ.setdefault("ETOZ_SEED_DEMO", "1")
    return subprocess.call(
        [sys.executable, "-m", "database.seed"],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
