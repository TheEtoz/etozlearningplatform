"""Wipe the database and create a single production admin account.

Usage (PowerShell):
  $env:DATABASE_URL = "postgresql://…?sslmode=require"
  $env:ETOZ_RESET_CONFIRM = "YES"
  python scripts/reset_production_admin.py

Optional overrides:
  ETOZ_ADMIN_USERNAME, ETOZ_ADMIN_EMAIL, ETOZ_ADMIN_PASSWORD
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from backend.config import normalize_database_url  # noqa: E402
from backend.security import hash_password  # noqa: E402


def main() -> int:
    if os.getenv("ETOZ_RESET_CONFIRM") != "YES":
        print(
            "Refusing reset. Set ETOZ_RESET_CONFIRM=YES to wipe the database.",
            file=sys.stderr,
        )
        return 1

    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    url = normalize_database_url(raw_url)
    username = (os.getenv("ETOZ_ADMIN_USERNAME") or "edbert wisely").strip()
    email = (os.getenv("ETOZ_ADMIN_EMAIL") or "edbertwisely@gmail.com").strip().lower()
    password = os.getenv("ETOZ_ADMIN_PASSWORD") or "Glenoy123"

    if len(username) < 3 or len(password) < 8:
        print("Admin username/password do not meet minimum length.", file=sys.stderr)
        return 1

    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))

    # Re-create schema via Alembic, then insert admin.
    import subprocess

    code = subprocess.call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
    )
    if code != 0:
        return code

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    username, email, hashed_password, role,
                    email_verified, email_verified_at
                ) VALUES (
                    :username, :email, :hashed_password, 'admin',
                    true, :verified_at
                )
                """
            ),
            {
                "username": username,
                "email": email,
                "hashed_password": hash_password(password),
                "verified_at": datetime.now(UTC),
            },
        )
        count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()

    print(f"Database wiped. Admin created: {username!r} <{email}>")
    print(f"User rows now: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
