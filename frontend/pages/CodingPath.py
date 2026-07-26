"""Duolingo-style free-jump coding path for students."""

import importlib
import runpy
from pathlib import Path

runpy.run_path(
    str(
        next(
            path / "frontend" / "setup_path.py"
            for path in Path(__file__).resolve().parents
            if (path / "frontend" / "setup_path.py").is_file()
        )
    )
)

import streamlit as st

import frontend.utils.api as _api

importlib.reload(_api)

from frontend.utils.api import (
    APIError,
    get_coding_path,
    list_questions,
    run_code,
    submit_code,
)
from frontend.utils.guards import require_student
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.ui import render_preserved_text

st.set_page_config(page_title="Coding Path | ETOZ", page_icon="💻", layout="wide")
init_session_state()
require_student()

st.markdown(
    """
    <style>
    .path-line {
        border-left: 3px solid #0e7490;
        margin-left: 1.1rem;
        padding-left: 1.25rem;
    }
    .path-node {
        display: inline-block;
        width: 2.2rem;
        height: 2.2rem;
        border-radius: 999px;
        text-align: center;
        line-height: 2.2rem;
        font-weight: 700;
        margin-right: 0.6rem;
        color: white;
    }
    .node-done { background: #15803d; }
    .node-todo { background: #0e7490; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "path_active_question" not in st.session_state:
    st.session_state.path_active_question = None
if "path_editor" not in st.session_state:
    st.session_state.path_editor = ""
if "path_result" not in st.session_state:
    st.session_state.path_result = None

token = get_access_token()
st.title("Coding Path")
st.caption("Free jump — open any level. Green means you have passed it before.")
st.page_link("pages/Dashboard.py", label="Back to Dashboard", icon="📊")

try:
    modules = get_coding_path(token)
except APIError as error:
    st.error(str(error))
    st.stop()

if st.session_state.path_active_question is None:
    if not modules:
        st.info("No coding path yet. Ask a teacher to create modules.")
        st.stop()

    for module in modules:
        st.subheader(module["title"])
        st.caption(
            f"{module.get('difficulty_label') or 'Module'} · "
            f"{module.get('completed_count', 0)}/{module.get('total_count', 0)} done"
        )
        render_preserved_text(module.get("description") or "")
        st.markdown('<div class="path-line">', unsafe_allow_html=True)
        for level in module.get("levels") or []:
            done = level.get("is_completed")
            css = "node-done" if done else "node-todo"
            mark = "✓" if done else str(level.get("position", 0) + 1)
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(
                    f'<span class="path-node {css}">{mark}</span>'
                    f"**{level['title']}** · {level.get('difficulty')} · "
                    f"{', '.join(level.get('topics') or [])}",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                if st.button("Open", key=f"open_{level['question_id']}"):
                    # Load full student question for starter code.
                    try:
                        questions = list_questions(token, question_type="coding")
                    except APIError as error:
                        st.error(str(error))
                        st.stop()
                    match = next(
                        (
                            item
                            for item in questions
                            if item["id"] == level["question_id"]
                        ),
                        None,
                    )
                    st.session_state.path_active_question = match or {
                        "id": level["question_id"],
                        "title": level["title"],
                        "description": "",
                        "starter_code": "",
                    }
                    st.session_state.path_editor = (
                        st.session_state.path_active_question.get("starter_code") or ""
                    )
                    st.session_state.path_result = None
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()
else:
    question = st.session_state.path_active_question
    if st.button("← Back to path"):
        st.session_state.path_active_question = None
        st.rerun()

    st.subheader(question.get("title", "Coding level"))
    render_preserved_text(question.get("description") or "")
    st.session_state.path_editor = st.text_area(
        "Your Python code",
        value=st.session_state.path_editor,
        height=260,
        key=f"path_code_{question['id']}",
    )
    run_col, submit_col = st.columns(2)
    with run_col:
        if st.button("Run", use_container_width=True):
            try:
                st.session_state.path_result = {
                    "kind": "run",
                    "data": run_code(token, st.session_state.path_editor),
                }
            except APIError as error:
                st.error(str(error))
    with submit_col:
        if st.button("Submit", type="primary", use_container_width=True):
            try:
                st.session_state.path_result = {
                    "kind": "submit",
                    "data": submit_code(
                        token,
                        question["id"],
                        st.session_state.path_editor,
                    ),
                }
            except APIError as error:
                st.error(str(error))

    result = st.session_state.path_result
    if result:
        data = result["data"]
        if result["kind"] == "run":
            st.code(data.get("stdout") or "(no output)", language="text")
            if data.get("stderr"):
                st.error(data["stderr"])
        else:
            status = data.get("status")
            if status == "passed":
                st.success(
                    f"Passed · {data.get('tests_passed')}/{data.get('tests_total')}"
                )
            else:
                st.warning(
                    f"{status} · score {data.get('score')} · "
                    f"{data.get('tests_passed')}/{data.get('tests_total')}"
                )
            if data.get("stderr"):
                st.error(data["stderr"])
