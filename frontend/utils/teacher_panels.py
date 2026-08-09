"""Reusable teacher panels embedded under Class Manager."""

from __future__ import annotations

import streamlit as st

from frontend.utils.api import (
    APIError,
    create_question,
    create_subject,
    create_topic,
    delete_question,
    list_admin_questions,
    update_question,
)
from frontend.utils.ui import (
    bank_picker_filters,
    clear_widget_keys,
    mcq_choices_editor,
    question_summary_label,
    render_question_preview,
    render_student_question_view,
    subject_area_picker,
    success_banner,
    test_case_editor,
)


def render_question_bank_panel(
    token: str,
    subjects_tree: list[dict],
    *,
    key_prefix: str = "cls_qb",
) -> None:
    """Question bank create / browse / edit UI."""

    st.caption(
        "Create, edit, and reuse questions. Shared questions can be imported "
        "into quizzes and lectures; only the author can edit or delete them."
    )
    create_tab, browse_tab = st.tabs(["Create question", "Browse & edit"])

    with create_tab:
        editor_col, preview_col = st.columns([1.15, 1], gap="large")
        with editor_col:
            q_type = st.selectbox("Type", ["mcq", "coding"], key=f"{key_prefix}_type")
            title = st.text_input("Title", key=f"{key_prefix}_title")
            description = st.text_area(
                "Description / prompt (optional — Markdown or LaTeX)",
                height=140,
                key=f"{key_prefix}_desc",
            )
            difficulty = st.selectbox(
                "Difficulty",
                ["easy", "medium", "hard"],
                key=f"{key_prefix}_diff",
            )
            visibility = st.selectbox(
                "Sharing",
                ["public", "private"],
                format_func=lambda value: (
                    "Public — others can reuse (not edit) this item"
                    if value == "public"
                    else "Private — only you can see/use it"
                ),
                key=f"{key_prefix}_vis",
            )
            subject, areas = subject_area_picker(
                subjects_tree=subjects_tree,
                key_prefix=f"{key_prefix}_create",
            )

            choices: list[str] = []
            correct_answer: str | None = None
            starter_code = ""
            cases: list[dict] = []
            if q_type == "mcq":
                choices, correct_answer = mcq_choices_editor(f"{key_prefix}_mcq")
            else:
                starter_code = st.text_area(
                    "Starter code",
                    value='print("Hello")\n',
                    height=140,
                    key=f"{key_prefix}_starter",
                )
                cases = test_case_editor(f"{key_prefix}_cases")

            with st.expander("Add subject or area"):
                new_subject = st.text_input(
                    "New subject", key=f"{key_prefix}_new_subject"
                )
                if st.button("Create subject", key=f"{key_prefix}_mk_subject"):
                    if new_subject.strip():
                        try:
                            create_subject(token, new_subject.strip())
                            success_banner("Subject created.")
                            st.rerun()
                        except APIError as error:
                            st.error(str(error))
                new_area = st.text_input(
                    "New area under selected subject",
                    key=f"{key_prefix}_new_area_btn",
                )
                if st.button("Create area", key=f"{key_prefix}_mk_area"):
                    if new_area.strip():
                        try:
                            create_topic(token, new_area.strip(), subject=subject)
                            success_banner("Area created.")
                            st.rerun()
                        except APIError as error:
                            st.error(str(error))

            st.info("Nothing is saved until you press **Save to bank**.")
            if st.button(
                "Save to bank", type="primary", key=f"{key_prefix}_save_create"
            ):
                if not areas:
                    st.error("Pick or create at least one area inside the subject.")
                elif len((title or "").strip()) < 3:
                    st.error("Title needs at least 3 characters.")
                else:
                    payload = {
                        "title": title.strip(),
                        "description": description or "",
                        "type": q_type,
                        "difficulty": difficulty,
                        "subject": subject,
                        "topics": areas,
                        "visibility": visibility,
                        "language": "python",
                    }
                    try:
                        if q_type == "mcq":
                            if len(choices) < 2 or not correct_answer:
                                st.error("Add at least two options and pick the answer.")
                                st.stop()
                            payload["choices"] = choices
                            payload["correct_answer"] = correct_answer
                        else:
                            if not cases:
                                st.error(
                                    "Add at least one test case with expected output."
                                )
                                st.stop()
                            payload["starter_code"] = starter_code
                            payload["test_cases"] = cases
                        created = create_question(token, payload)
                        clear_widget_keys(f"{key_prefix}_")
                        success_banner(f"Saved: {created['title']}")
                        st.rerun()
                    except APIError as error:
                        st.error(str(error))

        with preview_col:
            st.markdown("#### Student view")
            st.caption("Preview only — not saved until you press Save to bank.")
            draft = {
                "id": "draft",
                "title": st.session_state.get(f"{key_prefix}_title") or "Untitled",
                "description": st.session_state.get(f"{key_prefix}_desc") or "",
                "type": st.session_state.get(f"{key_prefix}_type") or "mcq",
                "difficulty": st.session_state.get(f"{key_prefix}_diff") or "easy",
                "subject": subject,
                "topics": areas,
                "choices": choices,
                "starter_code": st.session_state.get(f"{key_prefix}_starter") or "",
            }
            with st.container(border=True):
                render_student_question_view(draft)

    with browse_tab:
        try:
            questions = list_admin_questions(token)
        except APIError as error:
            st.error(str(error))
            return

        if not questions:
            st.info("No questions in the bank yet.")
            return

        subject_filter = st.selectbox(
            "Filter by subject",
            ["all", *[item["name"] for item in subjects_tree]],
            key=f"{key_prefix}_browse_subject",
        )
        if subject_filter != "all":
            questions = [
                q
                for q in questions
                if (q.get("subject") or "python") == subject_filter
            ]

        mine_only = st.checkbox("Only my questions", key=f"{key_prefix}_mine_only")
        if mine_only:
            questions = [
                q for q in questions if q.get("can_edit") or q.get("can_delete")
            ]

        filtered = bank_picker_filters(
            questions,
            key_prefix=f"{key_prefix}_manage",
            allow_type_filter=True,
        )

        by_key: dict[str, list] = {}
        for question in filtered:
            subject_name = question.get("subject") or "python"
            areas = question.get("topics") or ["(no area)"]
            by_key.setdefault(f"{subject_name} / {areas[0]}", []).append(question)

        preview_limit = 50
        shown = 0
        if not filtered:
            st.info("No questions match this search.")
        for group, items in sorted(by_key.items()):
            st.markdown(f"##### {group}")
            for question in items:
                if shown >= preview_limit:
                    break
                shown += 1
                with st.expander(question_summary_label(question)):
                    st.markdown("##### Edit question")
                    render_question_edit_form(
                        token,
                        question,
                        subjects_tree=subjects_tree,
                        key_prefix=f"{key_prefix}_edit_{question['id']}",
                    )
                    with st.expander("Student preview", expanded=False):
                        render_student_question_view(question)
                        render_question_preview(question, show_answers=True)
                    if question.get("can_delete"):
                        if st.button(
                            "Delete my question",
                            key=f"{key_prefix}_del_{question['id']}",
                        ):
                            try:
                                delete_question(token, question["id"])
                                success_banner("Question deleted.")
                                st.rerun()
                            except APIError as error:
                                st.error(str(error))
            if shown >= preview_limit:
                break
        if len(filtered) > preview_limit:
            st.caption(
                f"Showing first {preview_limit} matches — refine search to narrow further."
            )


def render_question_edit_form(
    token: str,
    question: dict,
    *,
    subjects_tree: list[dict],
    key_prefix: str,
) -> None:
    """Full edit form for a bank question the teacher owns."""

    st.caption(
        "Saving updates this bank item everywhere it is used "
        "(quizzes and lecture practice)."
    )
    title = st.text_input(
        "Title",
        value=question.get("title") or "",
        key=f"{key_prefix}_title",
    )
    description = st.text_area(
        "Description / prompt",
        value=question.get("description") or "",
        height=120,
        key=f"{key_prefix}_desc",
    )
    difficulty = st.selectbox(
        "Difficulty",
        ["easy", "medium", "hard"],
        index=["easy", "medium", "hard"].index(
            question.get("difficulty")
            if question.get("difficulty") in ("easy", "medium", "hard")
            else "easy"
        ),
        key=f"{key_prefix}_diff",
    )
    visibility = st.selectbox(
        "Sharing",
        ["public", "private"],
        index=0 if question.get("visibility") == "public" else 1,
        format_func=lambda value: (
            "Public — others can reuse (not edit)"
            if value == "public"
            else "Private — only you"
        ),
        key=f"{key_prefix}_vis",
    )
    subject, areas = subject_area_picker(
        subjects_tree=subjects_tree,
        key_prefix=f"{key_prefix}_subj",
        default_subject=question.get("subject"),
        default_areas=question.get("topics") or [],
    )

    q_type = question.get("type") or "mcq"
    choices: list[str] = []
    correct_answer: str | None = None
    starter_code = ""
    cases: list[dict] = []
    if q_type == "mcq":
        choices, correct_answer = mcq_choices_editor(
            f"{key_prefix}_mcq",
            initial_choices=question.get("choices") or [],
            initial_correct=question.get("correct_answer"),
        )
    else:
        starter_code = st.text_area(
            "Starter code",
            value=question.get("starter_code") or "",
            height=140,
            key=f"{key_prefix}_starter",
        )
        cases = test_case_editor(
            f"{key_prefix}_cases",
            initial=question.get("test_cases") or [],
        )

    if st.button("Save changes", type="primary", key=f"{key_prefix}_save"):
        if len((title or "").strip()) < 3:
            st.error("Title needs at least 3 characters.")
            return
        if not areas:
            st.error("Pick at least one area.")
            return
        payload: dict = {
            "title": title.strip(),
            "description": description or "",
            "difficulty": difficulty,
            "subject": subject,
            "topics": areas,
            "visibility": visibility,
        }
        try:
            if q_type == "mcq":
                if len(choices) < 2 or not correct_answer:
                    st.error("Add at least two options and pick the answer.")
                    return
                payload["choices"] = choices
                payload["correct_answer"] = correct_answer
            else:
                if not cases:
                    st.error("Add at least one test case.")
                    return
                payload["starter_code"] = starter_code
                payload["test_cases"] = cases
            update_question(token, int(question["id"]), payload)
            success_banner("Question updated.")
            st.rerun()
        except APIError as error:
            st.error(str(error))
