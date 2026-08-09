"""Unit tests for module → subsection splitting."""

from frontend.utils.lecture_pages import (
    blocks_to_subsections,
    split_module_pages,
    subsections_to_blocks,
)


def test_no_markers_single_page() -> None:
    blocks = [
        {"type": "lecture", "payload": {"markdown": "A"}},
        {"type": "mcq", "question_id": 1},
    ]
    pages = split_module_pages(blocks)
    assert len(pages) == 1
    assert pages[0]["title"] == "Page 1"
    assert pages[0]["blocks"] == blocks


def test_page_markers_split_subtopics() -> None:
    blocks = [
        {"type": "page", "payload": {"title": "Intro"}},
        {"type": "lecture", "payload": {"markdown": "one"}},
        {"type": "page", "payload": {"title": "Practice"}},
        {"type": "mcq", "question_id": 2},
        {"type": "coding", "question_id": 3},
    ]
    pages = split_module_pages(blocks)
    assert [page["title"] for page in pages] == ["Intro", "Practice"]
    assert len(pages[0]["blocks"]) == 1
    assert len(pages[1]["blocks"]) == 2


def test_round_trip_subsections() -> None:
    blocks = [
        {"type": "page", "payload": {"title": "Matrix addition"}},
        {"type": "lecture", "payload": {"markdown": "A+B"}, "id": 10},
        {"type": "page", "payload": {"title": "Matrix multiplication"}},
        {"type": "lecture", "payload": {"markdown": "AB"}, "id": 11},
    ]
    subsections = blocks_to_subsections(blocks)
    assert [item["title"] for item in subsections] == [
        "Matrix addition",
        "Matrix multiplication",
    ]
    flat = subsections_to_blocks(subsections)
    assert [item["type"] for item in flat] == [
        "page",
        "lecture",
        "page",
        "lecture",
    ]
    assert flat[0]["payload"]["title"] == "Matrix addition"
    assert flat[2]["payload"]["title"] == "Matrix multiplication"
