"""Shared Streamlit UI helpers for teacher/student forms."""

from __future__ import annotations

import random
from typing import Any

import streamlit as st


def _content_render():
    """Import content_render lazily (avoids Streamlit stale-module ImportErrors)."""

    from frontend.utils import content_render as content_render

    return content_render


def classify_media_url(url: str) -> str:
    return _content_render().classify_media_url(url)


def media_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    return _content_render().media_from_payload(payload)


def media_items_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    return _content_render().media_items_from_payload(payload)


def render_download_link(url: str, label: str | None = None) -> None:
    _content_render().render_download_link(url, label)


def render_markdown_content(text: str, *, empty_caption: str | None = None) -> None:
    _content_render().render_markdown_content(text, empty_caption=empty_caption)


def render_media_item(item: dict[str, Any]) -> None:
    _content_render().render_media_item(item)


def render_media_items(items: list[dict[str, Any]]) -> None:
    _content_render().render_media_items(items)


def youtube_embed_url(url: str) -> str | None:
    return _content_render().youtube_embed_url(url)


def render_preserved_text(text: str) -> None:
    """Show teacher-authored text; compile LaTeX when present (never show raw)."""

    body = text or ""
    if "\\" in body or "$" in body:
        render_markdown_content(body)
        return
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"<p style='white-space:pre-wrap;line-height:1.55;margin:0.25rem 0 0.75rem 0;"
        f"color:inherit;'>{safe}</p>",
        unsafe_allow_html=True,
    )


def question_summary_label(question: dict) -> str:
    """Short label for lists and pickers."""

    subject = question.get("subject") or "—"
    areas = ", ".join(question.get("topics") or []) or "—"
    visibility = question.get("visibility") or "public"
    return (
        f"{question['title']} · {question.get('type')} · "
        f"{question.get('difficulty')} · {subject}/{areas} · {visibility}"
    )


def render_student_question_view(question: dict) -> None:
    """Exact student-facing look: prompt + choices or starter code (no answers)."""

    st.markdown(f"### {question.get('title') or 'Question'}")
    render_markdown_content(question.get("description") or "")
    subject = question.get("subject") or "—"
    areas = ", ".join(question.get("topics") or []) or "—"
    st.caption(f"{question.get('difficulty', '')} · {subject} · {areas}")

    if question.get("type") == "mcq":
        choices = question.get("choices") or []
        if not choices:
            st.info("No choices yet.")
            return
        st.radio(
            "Choose one",
            choices,
            index=None,
            key=f"student_preview_radio_{question.get('id', 'new')}_{len(choices)}",
            disabled=True,
        )
        return

    starter = question.get("starter_code") or ""
    st.text_area(
        "Your Python code",
        value=starter,
        height=180,
        disabled=True,
        key=f"student_preview_code_{question.get('id', 'new')}",
    )


def render_question_preview(question: dict, *, show_answers: bool = True) -> None:
    """Show prompt, MCQ options, or coding tests so teachers need not memorize IDs."""

    subject = question.get("subject") or "—"
    areas = ", ".join(question.get("topics") or []) or "—"
    st.caption(
        f"{question.get('type', '?').upper()} · "
        f"{question.get('difficulty', '?')} · "
        f"{subject} · areas: {areas}"
    )
    render_markdown_content(question.get("description") or "")

    if question.get("type") == "mcq":
        choices = question.get("choices") or []
        correct = question.get("correct_answer")
        if not choices:
            st.warning("No choices stored on this question.")
            return
        st.markdown("**Options**")
        for index, choice in enumerate(choices, start=1):
            marker = "✓" if show_answers and choice == correct else "•"
            st.markdown(f"{marker} {index}. {choice}")
        if show_answers and correct:
            st.success(f"Correct answer: {correct}")
        return

    starter = question.get("starter_code") or ""
    if starter.strip():
        st.markdown("**Starter code**")
        st.code(starter, language=question.get("language") or "python")
    cases = question.get("test_cases") or []
    st.markdown(f"**Test cases** ({len(cases)})")
    if not cases:
        st.caption("No test cases.")
        return
    for index, case in enumerate(cases, start=1):
        stdin = case.get("stdin", "")
        expected = case.get("expected_stdout", case.get("expected_output", ""))
        with st.expander(f"Case {index}", expanded=False):
            st.markdown("Input (stdin)")
            st.code(stdin if str(stdin) else "(empty)")
            st.markdown("Expected output")
            st.code(expected if str(expected) else "(empty)")


def filter_question_bank(
    questions: list[dict],
    *,
    search: str = "",
    qtype: str | None = None,
    topic: str | None = None,
    exclude_ids: set[int] | frozenset[int] | None = None,
) -> list[dict]:
    """Client-side filter for teacher bank pickers."""

    needle = search.strip().lower()
    excluded = exclude_ids or set()
    results: list[dict] = []
    for question in questions:
        if question["id"] in excluded:
            continue
        if qtype and qtype != "all" and question.get("type") != qtype:
            continue
        topics = question.get("topics") or []
        if topic and topic != "all" and topic not in topics:
            continue
        if needle:
            haystack = " ".join(
                [
                    str(question.get("id", "")),
                    question.get("title") or "",
                    question.get("description") or "",
                    question.get("subject") or "",
                    " ".join(topics),
                    " ".join(question.get("choices") or []),
                ]
            ).lower()
            if needle not in haystack:
                continue
        results.append(question)
    return results


def bank_picker_filters(
    questions: list[dict],
    *,
    key_prefix: str,
    allow_type_filter: bool = True,
) -> list[dict]:
    """Render search / type / area controls and return the filtered bank."""

    areas = sorted(
        {name for q in questions for name in (q.get("topics") or []) if name}
    )
    cols = st.columns([3, 1, 1] if allow_type_filter else [3, 1])
    search = cols[0].text_input(
        "Search",
        key=f"{key_prefix}_search",
        placeholder="Title, prompt, option text, subject, area, or id",
    )
    qtype = "all"
    if allow_type_filter:
        qtype = cols[1].selectbox(
            "Type",
            ["all", "mcq", "coding"],
            key=f"{key_prefix}_type",
        )
        area_col = cols[2]
    else:
        area_col = cols[1]
    area = area_col.selectbox(
        "Area",
        ["all", *areas],
        key=f"{key_prefix}_topic",
    )
    filtered = filter_question_bank(
        questions,
        search=search,
        qtype=qtype,
        topic=area,
    )
    st.caption(f"Showing {len(filtered)} of {len(questions)} bank questions")
    return filtered


def topic_picker(
    *,
    available: list[str],
    key_prefix: str,
    default: list[str] | None = None,
) -> list[str]:
    """Legacy area multi-select (prefer subject_area_picker)."""

    options = sorted({name.strip().lower() for name in available if name.strip()})
    selected = st.multiselect(
        "Areas",
        options=options,
        default=[t for t in (default or []) if t in options],
        key=f"{key_prefix}_topics",
        help="Areas inside the selected subject.",
    )
    new_topic = st.text_input(
        "Create a new area (optional)",
        key=f"{key_prefix}_new_topic",
        placeholder="e.g. recursion",
    )
    topics = list(selected)
    if new_topic.strip():
        name = new_topic.strip().lower()
        if name not in topics:
            topics.append(name)
    return topics


def subject_area_picker(
    *,
    subjects_tree: list[dict],
    key_prefix: str,
    default_subject: str | None = None,
    default_areas: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Pick a subject then areas via searchable filtered lists."""

    subject_names = [item["name"] for item in subjects_tree]
    if not subject_names:
        subject_names = ["python"]

    subject_search = st.text_input(
        "Search subjects",
        key=f"{key_prefix}_subject_search",
        placeholder="Filter: python, math, java…",
    )
    subject_needle = subject_search.strip().lower()
    filtered_subjects = [
        name
        for name in subject_names
        if not subject_needle or subject_needle in name.lower()
    ]
    if not filtered_subjects:
        st.caption("No subjects match that search.")
        filtered_subjects = subject_names

    default_index = 0
    if default_subject and default_subject in filtered_subjects:
        default_index = filtered_subjects.index(default_subject)
    elif default_subject and default_subject in subject_names:
        # Keep prior selection visible even if filtered out.
        filtered_subjects = [default_subject, *filtered_subjects]
        default_index = 0

    subject = st.selectbox(
        "Subject",
        filtered_subjects,
        index=default_index,
        key=f"{key_prefix}_subject",
        help="Broad track such as python, math, or java.",
    )

    area_names: list[str] = []
    for item in subjects_tree:
        if item["name"] == subject:
            area_names = sorted(area["name"] for area in item.get("areas") or [])
            break

    area_search = st.text_input(
        "Search areas",
        key=f"{key_prefix}_area_search",
        placeholder="Filter areas inside this subject…",
    )
    area_needle = area_search.strip().lower()
    filtered_areas = [
        name
        for name in area_names
        if not area_needle or area_needle in name.lower()
    ]
    default_selected = [a for a in (default_areas or []) if a in filtered_areas]
    selected = st.multiselect(
        "Areas inside this subject",
        options=filtered_areas,
        default=default_selected,
        key=f"{key_prefix}_areas",
        help="Search above, then select one or more areas.",
    )

    new_subject = ""
    new_area = ""
    with st.expander("Create new subject or area"):
        new_subject = st.text_input(
            "New subject name",
            key=f"{key_prefix}_create_subject",
            placeholder="e.g. java",
        )
        new_area = st.text_input(
            "New area under selected subject",
            key=f"{key_prefix}_new_area",
            placeholder="e.g. recursion",
        )
        st.caption(
            "Type a new subject to use it for this question, or a new area name "
            "to add it to the selection."
        )
        if new_subject.strip():
            st.caption(f"Will use subject: **{new_subject.strip().lower()}**")
            subject = new_subject.strip().lower()

    areas = list(selected)
    if new_area.strip():
        name = new_area.strip().lower()
        if name not in areas:
            areas.append(name)
    return subject, areas


def unsaved_changes_banner(has_unsaved: bool, *, message: str) -> None:
    """Show an explicit draft warning when Save has not been pressed."""

    if has_unsaved:
        st.warning(message)


def test_case_editor(key_prefix: str, initial: list[dict] | None = None) -> list[dict]:
    """Friendly stdin / expected-output editor instead of raw JSON."""

    state_key = f"{key_prefix}_cases"
    if state_key not in st.session_state:
        seed = initial or [{"stdin": "", "expected_stdout": ""}]
        st.session_state[state_key] = [
            {
                "stdin": str(case.get("stdin", "")),
                "expected_stdout": str(
                    case.get("expected_stdout", case.get("expected_output", ""))
                ),
            }
            for case in seed
        ] or [{"stdin": "", "expected_stdout": ""}]

    st.markdown("**Test cases**")
    st.caption(
        "Each case: what the program reads (stdin) and what it should print "
        "(expected output). Leave stdin empty if the program needs no input."
    )

    cases: list[dict[str, Any]] = st.session_state[state_key]
    remove_index: int | None = None

    for index, case in enumerate(cases):
        with st.container(border=True):
            st.markdown(f"Case {index + 1}")
            case["stdin"] = st.text_area(
                "Program input (stdin)",
                value=case.get("stdin", ""),
                key=f"{key_prefix}_stdin_{index}",
                height=80,
                placeholder="e.g. 2\\n3",
            )
            case["expected_stdout"] = st.text_area(
                "Expected printed output",
                value=case.get("expected_stdout", ""),
                key=f"{key_prefix}_out_{index}",
                height=80,
                placeholder="e.g. 5",
            )
            if len(cases) > 1 and st.button(
                "Remove this case",
                key=f"{key_prefix}_rm_{index}",
            ):
                remove_index = index

    if remove_index is not None:
        cases.pop(remove_index)
        st.session_state[state_key] = cases
        st.rerun()

    if st.button("Add another test case", key=f"{key_prefix}_add"):
        cases.append({"stdin": "", "expected_stdout": ""})
        st.session_state[state_key] = cases
        st.rerun()

    st.session_state[state_key] = cases
    return [
        {
            "stdin": item.get("stdin", ""),
            "expected_stdout": item.get("expected_stdout", ""),
        }
        for item in cases
        if str(item.get("expected_stdout", "")).strip() != ""
        or str(item.get("stdin", "")).strip() != ""
    ]


def clear_widget_keys(prefix: str) -> None:
    """Remove session keys that start with prefix so forms reset."""

    for key in list(st.session_state.keys()):
        if str(key).startswith(prefix):
            del st.session_state[key]


def mcq_choices_editor(
    key_prefix: str,
    *,
    initial_choices: list[str] | None = None,
    initial_correct: str | None = None,
) -> tuple[list[str], str | None]:
    """Edit MCQ options as separate entries and pick which entry is correct.

    Returns ``(choices, correct_answer)``. Empty / incomplete forms return
    ``([], None)`` so the caller can validate before save.
    """

    state_key = f"{key_prefix}__opts"
    if state_key not in st.session_state:
        seed = [str(item).strip() for item in (initial_choices or []) if str(item).strip()]
        while len(seed) < 2:
            seed.append("")
        st.session_state[state_key] = seed
        # Seed widget keys so existing bank choices actually appear in the inputs.
        for index, text in enumerate(st.session_state[state_key]):
            st.session_state[f"{key_prefix}__opt_{index}"] = text

    options = list(st.session_state[state_key])
    for index in range(len(options)):
        widget_key = f"{key_prefix}__opt_{index}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = options[index]
        else:
            options[index] = st.session_state[widget_key]

    st.caption("Each field is one option. Choose which entry is the correct answer.")
    remove_index: int | None = None
    for index in range(len(options)):
        cols = st.columns([8, 1])
        cols[0].text_input(
            f"Option {index + 1}",
            key=f"{key_prefix}__opt_{index}",
            placeholder=f"Option {index + 1}",
        )
        if len(options) > 2 and cols[1].button(
            "✕",
            key=f"{key_prefix}__rm_{index}",
            help="Remove this option",
        ):
            remove_index = index

    if remove_index is not None:
        refreshed = [
            st.session_state.get(f"{key_prefix}__opt_{index}", options[index])
            for index in range(len(options))
            if index != remove_index
        ]
        for index in range(len(options) + 2):
            st.session_state.pop(f"{key_prefix}__opt_{index}", None)
            st.session_state.pop(f"{key_prefix}__rm_{index}", None)
        st.session_state.pop(f"{key_prefix}__correct_idx", None)
        st.session_state[state_key] = refreshed
        st.rerun()

    if st.button("Add option", key=f"{key_prefix}__add"):
        options = [
            st.session_state.get(f"{key_prefix}__opt_{index}", options[index])
            for index in range(len(options))
        ]
        options.append("")
        st.session_state[state_key] = options
        st.rerun()

    options = [
        st.session_state.get(f"{key_prefix}__opt_{index}", options[index])
        for index in range(len(options))
    ]
    st.session_state[state_key] = options

    filled = [str(item).strip() for item in options if str(item).strip()]
    if len(filled) < 2:
        st.caption("Add at least two non-empty options.")
        return [], None

    default_index = 0
    if initial_correct:
        for index, text in enumerate(filled):
            if text == initial_correct:
                default_index = index
                break
    correct_key = f"{key_prefix}__correct_idx"
    if correct_key not in st.session_state:
        st.session_state[correct_key] = default_index

    # If options changed and stored index is out of range, clamp.
    if int(st.session_state[correct_key]) >= len(filled):
        st.session_state[correct_key] = 0

    selected = st.radio(
        "Correct option",
        options=list(range(len(filled))),
        format_func=lambda index: filled[index],
        key=correct_key,
    )
    return filled, filled[int(selected)]


def shuffled_mcq_choices(
    choices: list[str],
    *,
    cache_key: str,
    seed: int,
) -> list[str]:
    """Return a stable shuffled copy of choices for one student attempt."""

    if "shuffled_choices" not in st.session_state:
        st.session_state.shuffled_choices = {}
    bucket = st.session_state.shuffled_choices
    if cache_key not in bucket:
        shuffled = list(choices)
        random.Random(seed).shuffle(shuffled)
        bucket[cache_key] = shuffled
    return list(bucket[cache_key])


def success_banner(message: str) -> None:
    """Show toast + success box after a teacher save."""

    st.toast(message, icon="✅")
    st.success(message)
