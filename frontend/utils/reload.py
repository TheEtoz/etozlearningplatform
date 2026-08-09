"""Force-reload frontend utils so Streamlit picks up code changes."""

from __future__ import annotations

import importlib
import sys


_HELPER_MODULES = (
    "frontend.utils.public_mode",
    "frontend.utils.latex_markdown",
    "frontend.utils.content_render",
    "frontend.utils.lecture_pages",
    "frontend.utils.api",
    "frontend.utils.ui",
    "frontend.utils.guards",
    "frontend.utils.nav",
)


def reload_frontend_utils() -> None:
    """Drop and reimport helper modules so Streamlit cannot keep stale copies.

    A plain ``importlib.reload(ui)`` re-runs ``ui`` against whatever
    ``content_render`` is already in ``sys.modules``. If that copy is old,
    imports like ``media_from_payload`` fail. Clearing first forces a disk read.
    """

    for name in _HELPER_MODULES:
        sys.modules.pop(name, None)

    for name in _HELPER_MODULES:
        importlib.import_module(name)
