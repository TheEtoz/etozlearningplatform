"""Shared Streamlit UI helpers for teacher/student forms."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_preserved_text(text: str) -> None:
    """Show teacher-authored text with newlines preserved."""

    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f'<div style="white-space: pre-wrap; line-height: 1.5;">{safe}</div>',
        unsafe_allow_html=True,
    )


def question_summary_label(question: dict) -> str:
    """Short label for lists and pickers."""

    topics = ", ".join(question.get("topics") or []) or "—"
    return (
        f"#{question['id']} · {question['title']} · "
        f"{question.get('type')} · {question.get('difficulty')} · {topics}"
    )


def render_question_preview(question: dict, *, show_answers: bool = True) -> None:
    """Show prompt, MCQ options, or coding tests so teachers need not memorize IDs."""

    st.caption(
        f"{question.get('type', '?').upper()} · "
        f"{question.get('difficulty', '?')} · "
        f"topics: {', '.join(question.get('topics') or []) or '—'}"
    )
    render_preserved_text(question.get("description") or "")

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
    """Render search / type / topic controls and return the filtered bank."""

    topics = sorted(
        {name for q in questions for name in (q.get("topics") or []) if name}
    )
    cols = st.columns([3, 1, 1] if allow_type_filter else [3, 1])
    search = cols[0].text_input(
        "Search questions",
        key=f"{key_prefix}_search",
        placeholder="Title, prompt text, option text, topic, or #id",
    )
    qtype = "all"
    if allow_type_filter:
        qtype = cols[1].selectbox(
            "Type",
            ["all", "mcq", "coding"],
            key=f"{key_prefix}_type",
        )
        topic_col = cols[2]
    else:
        topic_col = cols[1]
    topic = topic_col.selectbox(
        "Topic",
        ["all", *topics],
        key=f"{key_prefix}_topic",
    )
    filtered = filter_question_bank(
        questions,
        search=search,
        qtype=qtype,
        topic=topic,
    )
    st.caption(f"Showing {len(filtered)} of {len(questions)} bank questions")
    return filtered


def topic_picker(
    *,
    available: list[str],
    key_prefix: str,
    default: list[str] | None = None,
) -> list[str]:
    """Searchable multi-select of topics plus optional new topic creation."""

    options = sorted({name.strip().lower() for name in available if name.strip()})
    selected = st.multiselect(
        "Topic areas",
        options=options,
        default=[t for t in (default or []) if t in options],
        key=f"{key_prefix}_topics",
        help="Search and select one or more topics. Add a new topic below if needed.",
    )
    new_topic = st.text_input(
        "Create a new topic area (optional)",
        key=f"{key_prefix}_new_topic",
        placeholder="e.g. recursion",
    )
    topics = list(selected)
    if new_topic.strip():
        name = new_topic.strip().lower()
        if name not in topics:
            topics.append(name)
    return topics


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


def success_banner(message: str) -> None:
    """Show toast + success box after a teacher save."""

    st.toast(message, icon="✅")
    st.success(message)
