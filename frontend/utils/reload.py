"""Optional force-reload of frontend utils (local Streamlit only)."""

from __future__ import annotations

import importlib
import os
import sys


_HELPER_MODULES = (
    "frontend.utils.public_mode",
    "frontend.utils.latex_markdown",
    "frontend.utils.tikz_render",
    "frontend.utils.content_render",
    "frontend.utils.lecture_pages",
    "frontend.utils.api",
    "frontend.utils.ui",
    "frontend.utils.guards",
    "frontend.utils.nav",
)


def _should_reload_helpers() -> bool:
    """Only reload on local machines when explicitly enabled.

    Production / Streamlit Cloud must keep imports cached — reloading on every
    page run makes every click feel slow.
    """

    flag = (os.getenv("ETOZ_RELOAD_UTILS") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    # Streamlit Community Cloud / Docker-style mounts: never reload.
    if os.path.exists("/mount/src") or os.path.exists("/app"):
        return False
    debug = (os.getenv("DEBUG") or "").strip().lower()
    return debug in {"1", "true", "yes", "on"}


def reload_frontend_utils() -> None:
    """Drop and reimport helper modules so Streamlit cannot keep stale copies.

    No-op in production so each Streamlit rerun stays fast.
    """

    if not _should_reload_helpers():
        return

    for name in _HELPER_MODULES:
        sys.modules.pop(name, None)

    for name in _HELPER_MODULES:
        importlib.import_module(name)
