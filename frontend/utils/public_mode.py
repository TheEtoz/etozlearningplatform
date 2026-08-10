"""Public demo mode helpers (no login required)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

GUEST_USER: dict = {
    "id": 0,
    "username": "Guest",
    "email": "",
    "role": "student",
    "is_verified": True,
}


def _setting(name: str, default: str = "") -> str:
    """Prefer Streamlit secrets (Cloud), then process env, then default."""

    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None and name in secrets:
            value = str(secrets[name]).strip()
            if value:
                return value
    except Exception:
        pass
    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return str(value)
    return default


def is_public_mode() -> bool:
    """Return True when guests may browse class content without logging in."""

    raw = _setting("PUBLIC_MODE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}
