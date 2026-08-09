"""Split / join module blocks into subsections (pages) for students and teachers."""

from __future__ import annotations

import uuid
from typing import Any


def split_module_pages(blocks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return ``[{title, blocks}, …]`` for student lecture navigation.

    Teachers insert a ``page`` block (title in payload) to start each subtopic.
    Modules without markers are one page containing every content block.
    """

    items = list(blocks or [])
    has_markers = any((block.get("type") or "") == "page" for block in items)
    if not has_markers:
        return [{"title": "Page 1", "blocks": items}]

    pages: list[dict[str, Any]] = []
    current_title: str | None = None
    current_blocks: list[dict[str, Any]] = []

    for block in items:
        if (block.get("type") or "") == "page":
            if current_title is not None or current_blocks:
                pages.append(
                    {
                        "title": current_title or f"Page {len(pages) + 1}",
                        "blocks": current_blocks,
                    }
                )
            title = str((block.get("payload") or {}).get("title") or "").strip()
            current_title = title or f"Page {len(pages) + 1}"
            current_blocks = []
            continue
        if current_title is None:
            current_title = "Page 1"
        current_blocks.append(block)

    if current_title is not None or current_blocks:
        pages.append(
            {
                "title": current_title or f"Page {len(pages) + 1}",
                "blocks": current_blocks,
            }
        )
    return pages or [{"title": "Page 1", "blocks": []}]


def blocks_to_subsections(blocks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Teacher editor model: subsections with their own lecture-flow blocks."""

    pages = split_module_pages(blocks)
    subsections: list[dict[str, Any]] = []
    for page in pages:
        subsections.append(
            {
                "_uid": uuid.uuid4().hex[:12],
                "title": page.get("title") or "Untitled subsection",
                "blocks": [
                    {
                        **dict(block),
                        "_uid": block.get("_uid")
                        or (
                            f"id{block['id']}"
                            if block.get("id")
                            else uuid.uuid4().hex[:12]
                        ),
                    }
                    for block in (page.get("blocks") or [])
                    if (block.get("type") or "") != "page"
                ],
            }
        )
    if not subsections:
        subsections = [
            {
                "_uid": uuid.uuid4().hex[:12],
                "title": "Untitled subsection",
                "blocks": [],
            }
        ]
    return subsections


def subsections_to_blocks(subsections: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Flatten subsections back to API ``page`` markers + content blocks."""

    flat: list[dict[str, Any]] = []
    for section in subsections or []:
        title = str(section.get("title") or "").strip() or "Untitled subsection"
        flat.append(
            {
                "type": "page",
                "payload": {"title": title},
                "question_id": None,
            }
        )
        for block in section.get("blocks") or []:
            if (block.get("type") or "") == "page":
                continue
            flat.append(
                {
                    "type": block.get("type") or "lecture",
                    "payload": dict(block.get("payload") or {}),
                    "question_id": block.get("question_id"),
                    "id": block.get("id"),
                    "_uid": block.get("_uid"),
                }
            )
    return flat
