"""
ETOZ Learning Platform — FastAPI Backend Entry Point

This is the main file that starts the backend API server.
FastAPI is a modern Python web framework for building APIs (Application Programming Interfaces).

Why this file exists:
    Every backend needs a single entry point — a file that tells the server
    "start here." This file creates the FastAPI application and defines
    the first route (Hello World).

How to run:
    From the project root (with venv activated):
        uvicorn backend.main:app --reload --port 8000

    Then open: http://localhost:8000
    API docs:  http://localhost:8000/docs
"""

from fastapi import FastAPI

# Create the FastAPI application instance.
# Think of `app` as the central hub that all routes connect to.
app = FastAPI(
    title="ETOZ Learning Platform API",
    description="Backend API for the ETOZ Python learning platform",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    """
    Hello World endpoint.

    When someone visits http://localhost:8000/, this function runs
    and returns a JSON response.

    Returns:
        A dictionary that FastAPI automatically converts to JSON.
    """
    return {"message": "Hello from ETOZ Learning Platform API!"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Used to verify the server is running. Deployment platforms
    (like Render) ping this endpoint to know if the app is alive.

    Returns:
        Status indicator for monitoring tools.
    """
    return {"status": "ok"}
