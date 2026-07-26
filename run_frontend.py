"""Launch Streamlit with the project root on PYTHONPATH."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
APP_FILE = PROJECT_ROOT / "frontend" / "app.py"


def main() -> None:
    """Start the Streamlit frontend from the project root."""

    load_dotenv(PROJECT_ROOT / ".env")
    env = os.environ.copy()
    frontend_port = env.get("FRONTEND_PORT", "8501")
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(PROJECT_ROOT)
        if not python_path
        else f"{PROJECT_ROOT}{os.pathsep}{python_path}"
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP_FILE),
            "--server.port",
            frontend_port,
        ],
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
