"""Run Alembic migrations against DATABASE_URL (Neon or local).

Usage (PowerShell):
  $env:DATABASE_URL = "postgresql+psycopg2://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"
  python scripts/migrate_neon.py

Or with a Neon URI (postgres://…) — backend.config normalizes the driver.
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
    return subprocess.call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
