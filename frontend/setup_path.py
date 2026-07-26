"""Load ``frontend/bootstrap.py`` without requiring ``frontend`` on ``sys.path``."""

import importlib.util
from pathlib import Path


def setup_project_path() -> None:
    """Execute the bootstrap file that adds the project root to ``sys.path``."""

    bootstrap_file = next(
        path / "frontend" / "bootstrap.py"
        for path in Path(__file__).resolve().parents
        if (path / "frontend" / "bootstrap.py").is_file()
    )
    spec = importlib.util.spec_from_file_location("etoz_bootstrap", bootstrap_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load frontend bootstrap module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


setup_project_path()
