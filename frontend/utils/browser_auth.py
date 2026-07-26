"""Persist JWT across browser refresh using a cookie bridge."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


_COOKIE_NAME = "etoz_access_token"
_USER_COOKIE = "etoz_user_json"


def _write_cookies(token: str | None, user: dict | None) -> None:
    """Set or clear auth cookies in the browser."""

    if token:
        token_js = json.dumps(token)
        user_js = json.dumps(user or {})
        script = f"""
        <script>
        document.cookie = "{_COOKIE_NAME}=" + encodeURIComponent({token_js})
          + "; path=/; max-age=2592000; SameSite=Lax";
        document.cookie = "{_USER_COOKIE}=" + encodeURIComponent({user_js})
          + "; path=/; max-age=2592000; SameSite=Lax";
        </script>
        """
    else:
        script = f"""
        <script>
        document.cookie = "{_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax";
        document.cookie = "{_USER_COOKIE}=; path=/; max-age=0; SameSite=Lax";
        </script>
        """
    components.html(script, height=0)


def _read_cookie_from_context(name: str) -> str | None:
    """Read a cookie exposed by Streamlit's request context when available."""

    try:
        cookies = st.context.cookies
    except Exception:  # noqa: BLE001 — older Streamlit
        return None
    value = cookies.get(name)
    return value if value else None


def restore_auth_from_browser() -> tuple[str | None, dict[str, Any] | None]:
    """Return (token, user) from cookies if Streamlit can see them."""

    token = _read_cookie_from_context(_COOKIE_NAME)
    raw_user = _read_cookie_from_context(_USER_COOKIE)
    user = None
    if raw_user:
        try:
            user = json.loads(raw_user)
        except json.JSONDecodeError:
            user = None
    return token, user if isinstance(user, dict) else None


def persist_auth(token: str, user: dict) -> None:
    """Save auth into browser cookies."""

    _write_cookies(token, user)


def clear_persisted_auth() -> None:
    """Remove auth cookies."""

    _write_cookies(None, None)
