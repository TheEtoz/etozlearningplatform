"""Launch the FastAPI backend from the project root."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Start Uvicorn with reload enabled for local development."""

    load_dotenv(PROJECT_ROOT / ".env")
    backend_port = os.getenv("BACKEND_PORT", "8000")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            backend_port,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
