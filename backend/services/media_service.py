"""Local media library for lecture/question images, videos, and files."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from backend.config import settings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov"}
# Documents teachers may offer as downloads.
FILE_EXTENSIONS = {".pdf", ".zip", ".txt", ".csv", ".py", ".md"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | FILE_EXTENSIONS


class MediaServiceError(Exception):
    """Raised when an upload is rejected."""


def media_root_path() -> Path:
    root = Path(settings.media_root)
    if not root.is_absolute():
        # Project root = parent of backend/
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "file"


def classify_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return "file"


def public_media_url(stored_name: str) -> str:
    base = settings.public_api_url.rstrip("/")
    return f"{base}/media/{stored_name}"


def public_download_url(stored_name: str) -> str:
    """URL that forces Content-Disposition: attachment for browser download."""

    base = settings.public_api_url.rstrip("/")
    return f"{base}/media-download/{stored_name}"


def original_filename_from_stored(stored_name: str) -> str:
    """Strip the uuid prefix from ``abc123def456_name.pdf``."""

    if "_" in stored_name:
        return stored_name.split("_", 1)[1] or stored_name
    return stored_name


def resolve_stored_media(stored_name: str) -> Path:
    """Return a safe path under media_root or raise MediaServiceError."""

    safe = Path(stored_name).name
    if safe != stored_name or ".." in stored_name:
        raise MediaServiceError("Invalid media name")
    path = media_root_path() / safe
    if not path.is_file():
        raise MediaServiceError("Media not found")
    return path


def list_media_library() -> list[dict]:
    """List uploaded files newest-first for the teacher media picker."""

    root = media_root_path()
    rows: list[dict] = []
    for path in root.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        stored = path.name
        filename = original_filename_from_stored(stored)
        kind = classify_extension(filename)
        stat = path.stat()
        rows.append(
            {
                "filename": filename,
                "stored_name": stored,
                "url": public_media_url(stored),
                "download_url": public_download_url(stored),
                "path": f"/media/{stored}",
                "kind": kind,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    rows.sort(key=lambda item: item["modified_at"], reverse=True)
    return rows


def save_upload(*, filename: str, content: bytes, content_type: str | None) -> dict:
    """Persist bytes under media/ and return public URL metadata."""

    safe = _safe_filename(filename)
    ext = Path(safe).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise MediaServiceError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    max_bytes = settings.media_max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise MediaServiceError(
            f"File too large (max {settings.media_max_upload_mb} MB)."
        )
    if not content:
        raise MediaServiceError("Empty file")

    stored = f"{uuid.uuid4().hex[:12]}_{safe}"
    path = media_root_path() / stored
    path.write_bytes(content)
    kind = classify_extension(safe)
    url = public_media_url(stored)
    download_url = public_download_url(stored)
    # File/document kinds use the forced-download URL in student views.
    student_url = download_url if kind == "file" else url
    return {
        "filename": safe,
        "stored_name": stored,
        "url": student_url,
        "preview_url": url,
        "download_url": download_url,
        "path": f"/media/{stored}",
        "content_type": content_type or "application/octet-stream",
        "kind": kind,
        "size_bytes": len(content),
    }


def latex_snippet_for_media(
    *,
    url: str,
    kind: str,
    label: str | None = None,
) -> str:
    """Teacher-facing LaTeX snippet for lecture text (image or download link)."""

    if kind == "image":
        return f"\\includegraphics{{{url}}}"
    display = label or "Download file"
    return f"\\href{{{url}}}{{{display}}}"


def latex_snippet_for_url(url: str, *, label: str | None = None) -> str:
    """Build LaTeX for an image or a downloadable/open link in lecture text."""

    lowered = url.lower()
    if any(lowered.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return f"\\includegraphics{{{url}}}"
    text = label or url
    return f"\\href{{{url}}}{{{text}}}"
