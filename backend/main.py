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

from contextlib import asynccontextmanager
import logging
import mimetypes

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import check_database_connection
from backend.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from backend.routes.admin import router as admin_router
from backend.routes.auth import router as auth_router
from backend.routes.classes import router as classes_router
from backend.routes.code import router as code_router
from backend.routes.path import router as path_router
from backend.routes.progress import router as progress_router
from backend.routes.public import router as public_router
from backend.routes.questions import router as questions_router
from backend.routes.quizzes import router as quizzes_router
from backend.routes.submissions import router as submissions_router
from backend.routes.topics import router as topics_router
from backend.services.media_service import (
    MediaServiceError,
    media_root_path,
    original_filename_from_stored,
    resolve_stored_media,
)

logger = logging.getLogger(__name__)

DEFAULT_SECRET = "change-this-to-a-long-random-string"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup checks before serving requests."""

    if not settings.debug and settings.secret_key == DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY is still the default value. Set a strong secret "
            "before running with DEBUG=False."
        )

    try:
        check_database_connection()
        logger.info("Database connection successful.")
    except Exception as error:
        logger.error("Database connection failed: %s", error)

    media_dir = media_root_path()
    logger.info("Media library directory: %s", media_dir)

    yield


# Create the FastAPI application instance.
# Think of `app` as the central hub that all routes connect to.
app = FastAPI(
    title=f"{settings.app_name} API",
    description="Backend API for the ETOZ Python learning platform",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Middleware is applied in reverse order of addition.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(public_router, prefix="/api/v1")
app.include_router(topics_router, prefix="/api/v1")
app.include_router(classes_router, prefix="/api/v1")
app.include_router(quizzes_router, prefix="/api/v1")
app.include_router(questions_router, prefix="/api/v1")
app.include_router(path_router, prefix="/api/v1")
app.include_router(code_router, prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")
app.include_router(progress_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

@app.get("/media-download/{stored_name}")
def download_media_file(stored_name: str) -> FileResponse:
    """Force a browser download for teacher-uploaded files."""

    try:
        path = resolve_stored_media(stored_name)
    except MediaServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    filename = original_filename_from_stored(path.name)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="attachment",
    )


# Uploaded lecture/question media (images, videos — inline preview).
app.mount(
    "/media",
    StaticFiles(directory=str(media_root_path())),
    name="media",
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


@app.get("/health/db")
def database_health_check() -> dict[str, str]:
    """Verify that the API can reach PostgreSQL."""

    try:
        check_database_connection()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {error}",
        ) from error

    return {"status": "ok", "database": "connected"}
