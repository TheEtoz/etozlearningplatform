"""Promote an existing user to the admin role.

Usage (from project root, venv active):
    python -m database.promote_admin teacher
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from backend.database import SessionLocal
from backend.models.user import User


def promote(username: str) -> bool:
    """Set role=admin for the given username. Return True if updated."""

    with SessionLocal() as database:
        user = database.scalars(
            select(User).where(User.username == username)
        ).first()
        if user is None:
            print(f"User not found: {username}")
            return False
        user.role = "admin"
        database.commit()
        print(f"Promoted '{username}' to admin.")
        return True


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m database.promote_admin <username>")
        return 1
    return 0 if promote(args[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
