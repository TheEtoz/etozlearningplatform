"""Persist JWT across browser refresh using a cookie bridge.

Streamlit cannot set HttpOnly cookies from Python. Tokens are therefore
readable by JavaScript on the Streamlit origin (XSS risk). Mitigations:
short JWT TTL on the API, SameSite=Lax, Secure on HTTPS, and never render
untrusted HTML. Prefer a reverse-proxy HttpOnly session for production.

Cookies must be written on the *parent* page via components.html — an
st.iframe srcdoc cookie only applies to the iframe, so refresh would lose
the session.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import unquote, urlparse

import streamlit as st
import streamlit.components.v1 as components

_COOKIE_NAME = "etoz_access_token"
_USER_COOKIE = "etoz_user_json"
_MAX_AGE = 2_592_000  # 30 days


def _cookie_secure_flag() -> str:
    """Add Secure only when the Streamlit page itself is HTTPS.

    Do not key off BACKEND_URL — a HTTPS API with an HTTP localhost
    frontend would make the browser reject the cookie.
    """

    try:
        page_url = getattr(st.context, "url", None)
        if page_url and str(page_url).lower().startswith("https:"):
            return "; Secure"
    except Exception:  # noqa: BLE001 — context unavailable
        pass
    for key in ("STREAMLIT_SERVER_URL", "FRONTEND_URL"):
        raw = (os.getenv(key) or "").strip()
        if raw and urlparse(raw).scheme == "https":
            return "; Secure"
    return ""


def _write_cookies(token: str | None, user: dict | None) -> None:
    """Set or clear auth cookies on the parent Streamlit document."""

    secure = _cookie_secure_flag()
    if token:
        token_js = json.dumps(token)
        user_js = json.dumps(user or {}, separators=(",", ":"))
        script = f"""
        <script>
        (function () {{
          var doc = window.parent.document;
          doc.cookie = "{_COOKIE_NAME}=" + encodeURIComponent({token_js})
            + "; path=/; max-age={_MAX_AGE}; SameSite=Lax{secure}";
          doc.cookie = "{_USER_COOKIE}=" + encodeURIComponent({user_js})
            + "; path=/; max-age={_MAX_AGE}; SameSite=Lax{secure}";
        }})();
        </script>
        """
    else:
        script = f"""
        <script>
        (function () {{
          var doc = window.parent.document;
          doc.cookie = "{_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax{secure}";
          doc.cookie = "{_USER_COOKIE}=; path=/; max-age=0; SameSite=Lax{secure}";
        }})();
        </script>
        """
    components.html(script, height=0, width=0)


def _read_cookie_from_context(name: str) -> str | None:
    """Read a cookie exposed by Streamlit's request context when available."""

    try:
        cookies = st.context.cookies
    except Exception:  # noqa: BLE001 — older Streamlit
        return None
    value = cookies.get(name)
    if not value:
        return None
    return unquote(value)


def restore_auth_from_browser() -> tuple[str | None, dict[str, Any] | None]:
    """Return (token, user) from cookies if Streamlit can see them."""

    token = _read_cookie_from_context(_COOKIE_NAME)
    raw_user = _read_cookie_from_context(_USER_COOKIE)
    user = None
    if raw_user:
        try:
            parsed = json.loads(raw_user)
            if isinstance(parsed, dict):
                user = parsed
        except json.JSONDecodeError:
            user = None
    return token, user


def persist_auth(token: str, user: dict) -> None:
    """Save auth into browser cookies and give the browser a moment to apply."""

    _write_cookies(token, user)
    # switch_page / rerun can abort before the component runs; brief pause helps.
    time.sleep(0.35)


def clear_persisted_auth() -> None:
    """Remove auth cookies."""

    _write_cookies(None, None)
    time.sleep(0.2)
