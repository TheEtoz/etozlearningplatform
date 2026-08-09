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
    """Read from process env, then Streamlit secrets (Community Cloud)."""

    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return str(value)
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None and name in secrets:
            return str(secrets[name])
    except Exception:
        pass
    return default


def is_public_mode() -> bool:
    """Return True when guests may browse class content without logging in."""

    raw = _setting("PUBLIC_MODE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}
