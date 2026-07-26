"""Teacher question bank — topics, friendly test cases, clear-after-save."""

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
    create_question,
    create_topic,
    delete_question,
    list_admin_questions,
    list_topics,
    update_question,
)
from frontend.utils.guards import require_teacher
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.ui import (
    bank_picker_filters,
    clear_widget_keys,
    question_summary_label,
    render_preserved_text,
    render_question_preview,
    success_banner,
    test_case_editor,
    topic_picker,
)

st.set_page_config(page_title="Question Bank | ETOZ", page_icon="📚", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

st.title("Question Bank")
st.caption("Create reusable MCQ and coding items. Attach them later to quizzes or the path.")

try:
    topic_options = [t["name"] for t in list_topics(token)]
except APIError as error:
    st.error(str(error))
    topic_options = []

create_tab, manage_tab = st.tabs(["Create question", "Manage bank"])

with create_tab:
    with st.form("create_question_form", clear_on_submit=False):
        q_type = st.selectbox("Type", ["mcq", "coding"], key="qb_type")
        title = st.text_input("Title", key="qb_title")
        description = st.text_area(
            "Description / prompt",
            height=140,
            key="qb_desc",
            help="Line breaks are kept when students see this question.",
        )
        difficulty = st.selectbox(
            "Difficulty",
            ["easy", "medium", "hard"],
            key="qb_diff",
        )
        topics = topic_picker(
            available=topic_options,
            key_prefix="qb_create",
        )

        choices_text = ""
        correct_answer = ""
        starter_code = ""
        if q_type == "mcq":
            choices_text = st.text_area(
                "Choices (one per line)",
                height=120,
                key="qb_choices",
            )
            correct_answer = st.text_input("Correct answer", key="qb_correct")
        else:
            starter_code = st.text_area(
                "Starter code",
                value='print("Hello")\n',
                height=140,
                key="qb_starter",
            )
            # Test cases live outside the form submit snapshot via session state;
            # we still show the editor here for UX and read it on submit.
            st.caption("Add test cases below the form buttons area.")

        submitted = st.form_submit_button("Save to bank", type="primary")

    if q_type == "coding":
        cases = test_case_editor("qb_create_cases")
    else:
        cases = []

    with st.expander("Quick-add a topic to the list"):
        new_only = st.text_input("New topic name", key="qb_topic_only")
        if st.button("Create topic"):
            if new_only.strip():
                try:
                    create_topic(token, new_only.strip())
                    success_banner(f'Topic "{new_only.strip().lower()}" created.')
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

    if submitted:
        if not topics:
            st.error("Pick or create at least one topic area.")
        else:
            payload = {
                "title": title,
                "description": description,
                "type": q_type,
                "difficulty": difficulty,
                "topics": topics,
                "language": "python",
            }
            try:
                if q_type == "mcq":
                    payload["choices"] = [
                        line.strip()
                        for line in choices_text.splitlines()
                        if line.strip()
                    ]
                    payload["correct_answer"] = correct_answer
                else:
                    if not cases:
                        st.error("Add at least one test case with expected output.")
                        st.stop()
                    payload["starter_code"] = starter_code
                    payload["test_cases"] = cases
                created = create_question(token, payload)
                clear_widget_keys("qb_")
                success_banner(
                    f"Saved question #{created['id']}: {created['title']}"
                )
                st.rerun()
            except APIError as error:
                st.error(str(error))

with manage_tab:
    try:
        questions = list_admin_questions(token)
    except APIError as error:
        st.error(str(error))
        st.stop()

    if not questions:
        st.info("No questions in the bank yet.")
        st.stop()

    filtered = bank_picker_filters(
        questions,
        key_prefix="qb_manage",
        allow_type_filter=True,
    )
    preview_limit = 50
    if not filtered:
        st.info("No questions match this search.")
    for question in filtered[:preview_limit]:
        with st.expander(question_summary_label(question)):
            st.markdown("##### Preview")
            render_question_preview(question, show_answers=True)
            st.divider()
            st.markdown("##### Edit")
            new_title = st.text_input(
                "Title",
                value=question["title"],
                key=f"qb_edit_title_{question['id']}",
            )
            new_desc = st.text_area(
                "Description",
                value=question["description"],
                key=f"qb_edit_desc_{question['id']}",
                height=120,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Update", key=f"qb_save_{question['id']}"):
                    try:
                        update_question(
                            token,
                            question["id"],
                            {"title": new_title, "description": new_desc},
                        )
                        success_banner("Question updated.")
                        st.rerun()
                    except APIError as error:
                        st.error(str(error))
            with c2:
                if st.button("Delete", key=f"qb_del_{question['id']}"):
                    try:
                        delete_question(token, question["id"])
                        success_banner("Question deleted.")
                        st.rerun()
                    except APIError as error:
                        st.error(str(error))
    if len(filtered) > preview_limit:
        st.caption(
            f"Showing first {preview_limit} matches — refine search to narrow further."
        )
