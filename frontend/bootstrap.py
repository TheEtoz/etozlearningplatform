"""Add the project root to ``sys.path`` for Streamlit scripts.

Streamlit executes files inside ``frontend/`` and ``frontend/pages/``, so Python
does not automatically treat ``frontend`` as an importable package. This module
finds the project root and adds it to ``sys.path`` before other imports run.
"""

import sys
from pathlib import Path


def ensure_project_root_on_path() -> None:
    """Insert the repository root into ``sys.path`` if it is missing."""

    for path in Path(__file__).resolve().parents:
        if (path / "frontend" / "utils").is_dir() and (path / "backend").is_dir():
            project_root = str(path)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            return

    raise RuntimeError("Could not locate the ETOZ project root.")


ensure_project_root_on_path()
