"""Teacher quiz manager — timed settings, bank import, create-and-attach."""

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
    create_quiz,
    delete_quiz,
    list_admin_questions,
    list_admin_quizzes,
    list_topics,
    set_quiz_questions,
    update_quiz,
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

st.set_page_config(page_title="Quiz Manager | ETOZ", page_icon="📝", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

st.title("Quiz Manager")
st.caption(
    "Design quizzes: set a timer, import bank questions, or create a new question "
    "that is saved to the bank and attached here."
)

try:
    topic_options = [t["name"] for t in list_topics(token)]
except APIError:
    topic_options = []

create_tab, manage_tab = st.tabs(["Create quiz", "Manage quizzes"])

with create_tab:
    with st.form("create_quiz_form"):
        title = st.text_input("Quiz title")
        description = st.text_area(
            "Description",
            height=100,
            help="Line breaks are shown to students as you type them.",
        )
        is_timed = st.checkbox("Timed quiz")
        duration = st.number_input("Duration (seconds)", min_value=30, value=120, step=30)
        submitted = st.form_submit_button("Create quiz", type="primary")
    if submitted:
        try:
            quiz = create_quiz(
                token,
                {
                    "title": title,
                    "description": description,
                    "is_timed": is_timed,
                    "duration_seconds": int(duration) if is_timed else None,
                },
            )
            success_banner(
                f"Created quiz #{quiz['id']}. Open Manage quizzes to add questions."
            )
            st.rerun()
        except APIError as error:
            st.error(str(error))

with manage_tab:
    try:
        quizzes = list_admin_quizzes(token)
        bank = list_admin_questions(token)
    except APIError as error:
        st.error(str(error))
        st.stop()

    if not quizzes:
        st.info("No quizzes yet — create one in the other tab.")
        st.stop()

    id_to_question = {q["id"]: q for q in bank}
    selected_quiz_label = st.selectbox(
        "Choose a quiz to edit",
        options=[f"#{q['id']} · {q['title']}" for q in quizzes],
    )
    quiz = next(
        q
        for q in quizzes
        if f"#{q['id']} · {q['title']}" == selected_quiz_label
    )

    st.subheader(quiz["title"])
    render_preserved_text(quiz["description"])
    st.caption(
        (
            f"Timed · {quiz['duration_seconds']}s"
            if quiz["is_timed"]
            else "Untimed"
        )
        + f" · topics: {', '.join(quiz.get('topics') or []) or '—'}"
    )

    server_ids = list(quiz.get("question_ids") or [])
    order_key = f"quiz_order_{quiz['id']}"
    server_snap_key = f"quiz_server_{quiz['id']}"
    # Refresh the draft only when the saved server list changes (not on local edits).
    if (
        order_key not in st.session_state
        or st.session_state.get(server_snap_key) != server_ids
    ):
        st.session_state[order_key] = list(server_ids)
        st.session_state[server_snap_key] = list(server_ids)

    settings, members, add_new, danger = st.tabs(
        ["Settings", "Questions in quiz", "Add new question", "Delete"]
    )

    with settings:
        timed = st.checkbox("Timed", value=quiz["is_timed"], key=f"timed_{quiz['id']}")
        duration_val = st.number_input(
            "Duration seconds",
            min_value=30,
            value=int(quiz["duration_seconds"] or 120),
            key=f"dur_{quiz['id']}",
        )
        if st.button("Save settings", type="primary"):
            try:
                update_quiz(
                    token,
                    quiz["id"],
                    {
                        "is_timed": timed,
                        "duration_seconds": int(duration_val) if timed else None,
                    },
                )
                success_banner("Quiz settings updated.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

    with members:
        order = list(st.session_state[order_key])

        st.markdown("#### Current quiz questions")
        st.caption(
            "Open each item to read the prompt and options. Use ↑ ↓ to reorder, ✕ to remove."
        )
        if not order:
            st.info("This quiz has no questions yet — add from the bank below.")
        for index, qid in enumerate(order):
            question = id_to_question.get(qid)
            header = (
                question_summary_label(question)
                if question
                else f"#{qid} · (missing from bank)"
            )
            cols = st.columns([8, 1, 1, 1])
            with cols[0]:
                with st.expander(f"{index + 1}. {header}", expanded=False):
                    if question:
                        render_question_preview(question, show_answers=True)
                    else:
                        st.warning(
                            "This question id is on the quiz but not in the loaded bank."
                        )
            if cols[1].button("↑", key=f"qup_{quiz['id']}_{qid}", disabled=index == 0):
                order[index - 1], order[index] = order[index], order[index - 1]
                st.session_state[order_key] = order
                st.rerun()
            if cols[2].button(
                "↓",
                key=f"qdn_{quiz['id']}_{qid}",
                disabled=index >= len(order) - 1,
            ):
                order[index + 1], order[index] = order[index], order[index + 1]
                st.session_state[order_key] = order
                st.rerun()
            if cols[3].button("✕", key=f"qrm_{quiz['id']}_{qid}"):
                order.pop(index)
                st.session_state[order_key] = order
                st.rerun()

        if st.button("Save question list", type="primary", key=f"qsave_{quiz['id']}"):
            try:
                set_quiz_questions(token, quiz["id"], order)
                st.session_state[server_snap_key] = list(order)
                success_banner("Quiz questions updated.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

        st.divider()
        st.markdown("#### Add from question bank")
        available = [q for q in bank if q["id"] not in set(order)]
        filtered = bank_picker_filters(
            available,
            key_prefix=f"quiz_bank_{quiz['id']}",
            allow_type_filter=True,
        )
        if not filtered:
            st.info("No matching bank questions left to add.")
        else:
            preview_limit = 25
            for question in filtered[:preview_limit]:
                with st.expander(question_summary_label(question), expanded=False):
                    render_question_preview(question, show_answers=True)
                    if st.button(
                        "Add to quiz",
                        key=f"qadd_{quiz['id']}_{question['id']}",
                        type="primary",
                    ):
                        order.append(question["id"])
                        st.session_state[order_key] = order
                        st.rerun()
            if len(filtered) > preview_limit:
                st.caption(
                    f"Showing first {preview_limit} matches — refine search to narrow further."
                )

    with add_new:
        st.write("Creates a bank question and appends it to this quiz.")
        ntype = st.selectbox("Type", ["mcq", "coding"], key=f"ntype_{quiz['id']}")
        ntitle = st.text_input("Title", key=f"ntitle_{quiz['id']}")
        ndesc = st.text_area("Description", key=f"ndesc_{quiz['id']}", height=120)
        ntopics = topic_picker(
            available=topic_options,
            key_prefix=f"nquiz_{quiz['id']}",
        )
        if ntype == "mcq":
            nchoices = st.text_area("Choices one per line", key=f"nchoices_{quiz['id']}")
            ncorrect = st.text_input("Correct answer", key=f"ncorrect_{quiz['id']}")
            ncases = []
        else:
            ncode = st.text_area(
                "Starter code",
                value='print("ok")\n',
                key=f"ncode_{quiz['id']}",
            )
            ncases = test_case_editor(f"nquiz_cases_{quiz['id']}")
        if st.button("Create & attach", type="primary", key=f"attach_{quiz['id']}"):
            if not ntopics:
                st.error("Choose at least one topic.")
            else:
                payload = {
                    "title": ntitle,
                    "description": ndesc,
                    "type": ntype,
                    "difficulty": "easy",
                    "topics": ntopics,
                    "language": "python",
                }
                try:
                    if ntype == "mcq":
                        payload["choices"] = [
                            line.strip()
                            for line in nchoices.splitlines()
                            if line.strip()
                        ]
                        payload["correct_answer"] = ncorrect
                    else:
                        if not ncases:
                            st.error("Add at least one test case.")
                            st.stop()
                        payload["starter_code"] = ncode
                        payload["test_cases"] = ncases
                    created = create_question(token, payload)
                    new_ids = list(st.session_state.get(order_key, server_ids))
                    if created["id"] not in new_ids:
                        new_ids.append(created["id"])
                    set_quiz_questions(token, quiz["id"], new_ids)
                    st.session_state[order_key] = new_ids
                    st.session_state[server_snap_key] = list(new_ids)
                    clear_widget_keys(f"nquiz_{quiz['id']}")
                    clear_widget_keys(f"ntype_{quiz['id']}")
                    clear_widget_keys(f"ntitle_{quiz['id']}")
                    clear_widget_keys(f"ndesc_{quiz['id']}")
                    success_banner(f"Added question #{created['id']} to the quiz.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

    with danger:
        st.warning("Deleting a quiz does not delete bank questions.")
        if st.button("Delete this quiz", type="primary"):
            try:
                delete_quiz(token, quiz["id"])
                success_banner("Quiz deleted.")
                st.rerun()
            except APIError as error:
                st.error(str(error))
