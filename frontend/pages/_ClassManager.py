"""Teacher class manager — settings, quizzes, modules/lectures, announcements."""

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

from frontend.utils.api import (
    APIError,
    clone_question,
    clone_quiz,
    create_class,
    create_class_announcement,
    create_module,
    create_question,
    create_quiz,
    delete_class,
    delete_class_announcement,
    delete_module,
    delete_quiz,
    get_class_performance,
    list_admin_modules,
    list_admin_questions,
    list_admin_quizzes,
    list_class_announcements,
    list_my_classes,
    list_subjects,
    regenerate_class_code,
    set_class_modules,
    set_class_quizzes,
    set_quiz_questions,
    update_class,
    update_question,
    update_quiz,
)
from frontend.utils.guards import require_teacher
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.teacher_panels import (
    render_question_bank_panel,
    render_question_edit_form,
)
from frontend.utils.ui import (
    bank_picker_filters,
    clear_widget_keys,
    mcq_choices_editor,
    question_summary_label,
    render_preserved_text,
    render_question_preview,
    subject_area_picker,
    success_banner,
    test_case_editor,
    unsaved_changes_banner,
)

st.set_page_config(page_title="Classes | ETOZ", page_icon="🏫", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

st.title("Classes")
st.caption(
    "Create a class, then manage quizzes and modules here. "
    "Nothing auto-saves — use the Save buttons."
)

flash = st.session_state.pop("cls_flash", None)
if flash:
    st.success(flash)

try:
    subjects_tree = list_subjects(token)
except APIError:
    subjects_tree = []

if st.session_state.pop("cls_goto_manage", False):
    st.session_state.cls_hub_mode = "Manage classes"
if "cls_hub_mode" not in st.session_state:
    st.session_state.cls_hub_mode = "Manage classes"

mode = st.radio(
    "View",
    ["Create class", "Manage classes"],
    horizontal=True,
    key="cls_hub_mode",
    label_visibility="collapsed",
)

if mode == "Create class":
    st.markdown("#### Create a new class")
    title = st.text_input(
        "Class title",
        key="cls_new_title",
        placeholder="Intro Python — Cohort A",
    )
    description = st.text_area(
        "Description (optional)",
        key="cls_new_desc",
        height=120,
        placeholder="What this class covers...",
    )
    visibility = st.selectbox(
        "Join style",
        ["private", "public"],
        key="cls_new_vis",
        help="Private = enrollment code only. Public = students can browse and join.",
    )
    if st.button("Create class", type="primary", key="cls_new_submit"):
        if len((title or "").strip()) < 3:
            st.error("Class title needs at least 3 characters.")
        else:
            try:
                created = create_class(
                    token,
                    {
                        "title": title.strip(),
                        "description": description,
                        "visibility": visibility,
                    },
                )
                st.session_state["managed_class_id"] = created["id"]
                st.session_state["cls_goto_manage"] = True
                st.session_state["cls_flash"] = (
                    f"Class **{created['title']}** created. "
                    f"Enrollment code: `{created.get('enrollment_code')}` — "
                    "you can manage it below."
                )
                clear_widget_keys("cls_new_")
                st.rerun()
            except APIError as error:
                st.error(str(error))
else:
    try:
        classes = list_my_classes(token)
        all_quizzes = list_admin_quizzes(token)
        bank = list_admin_questions(token)
    except APIError as error:
        st.error(str(error))
        st.stop()

    if not classes:
        st.info("No classes yet — switch to **Create class** above.")
        st.stop()

    id_to_quiz = {q["id"]: q for q in all_quizzes}
    id_to_question = {q["id"]: q for q in bank}
    teacher_id = (st.session_state.get("current_user") or {}).get("id")

    preferred = st.session_state.get("managed_class_id")
    labels = {}
    for item in classes:
        status = "active" if item.get("is_active", True) else "inactive"
        labels[
            f"{item['title']} ({item['visibility']} · {status})"
        ] = item
    label_list = list(labels.keys())
    default_index = 0
    if preferred is not None:
        for index, item in enumerate(classes):
            if item["id"] == preferred:
                default_index = index
                break

    choice = st.selectbox(
        "Class to manage",
        options=label_list,
        index=default_index,
        key="cls_manage_pick",
    )
    classroom = labels[choice]
    class_id = classroom["id"]
    st.session_state["managed_class_id"] = class_id

    st.subheader(classroom["title"])
    if not classroom.get("is_active", True):
        st.warning(
            "This class is inactive — students cannot see or join it. "
            "Turn **Active** back on in Settings and save."
        )
    render_preserved_text(classroom.get("description") or "")
    st.caption(
        f"{classroom['visibility'].title()} · "
        f"{'Active' if classroom.get('is_active', True) else 'Inactive'} · "
        f"{classroom.get('student_count', 0)} enrolled · "
        f"{classroom.get('quiz_count', 0)} quizzes · "
        f"{classroom.get('module_count', 0)} modules · "
        f"code **{classroom.get('enrollment_code') or '—'}**"
    )

    (
        settings,
        quizzes_tab,
        modules_tab,
        bank_tab,
        announcements,
        performance,
    ) = st.tabs(
        [
            "Settings",
            "Quizzes",
            "Modules",
            "Question bank",
            "Announcements",
            "Performance",
        ]
    )

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #
    with settings:
        new_title = st.text_input(
            "Title",
            value=classroom["title"],
            key=f"cls_title_{class_id}",
        )
        new_desc = st.text_area(
            "Description (optional)",
            value=classroom.get("description") or "",
            key=f"cls_desc_{class_id}",
            height=120,
        )
        new_vis = st.selectbox(
            "Join style",
            ["private", "public"],
            index=0 if classroom.get("visibility") == "private" else 1,
            key=f"cls_vis_{class_id}",
        )
        active = st.checkbox(
            "Active",
            value=bool(classroom.get("is_active", True)),
            key=f"cls_active_{class_id}",
        )
        settings_dirty = (
            new_title != classroom["title"]
            or (new_desc or "") != (classroom.get("description") or "")
            or new_vis != classroom.get("visibility")
            or bool(active) != bool(classroom.get("is_active", True))
        )
        unsaved_changes_banner(
            settings_dirty,
            message="Class settings changed — press Save settings or leave and lose them.",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save settings", type="primary", key=f"cls_save_{class_id}"):
                try:
                    update_class(
                        token,
                        class_id,
                        {
                            "title": new_title,
                            "description": new_desc,
                            "visibility": new_vis,
                            "is_active": active,
                        },
                    )
                    success_banner("Class settings saved.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))
        with c2:
            if st.button("Regenerate enrollment code", key=f"cls_code_{class_id}"):
                try:
                    updated = regenerate_class_code(token, class_id)
                    success_banner(f"New code: {updated.get('enrollment_code')}")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

        st.divider()
        st.markdown("#### Delete class")
        st.caption(
            "Permanently removes this class, enrollments, lectures, and "
            "announcements. Quizzes in your bank are kept."
        )
        confirm_title = st.text_input(
            "Type the class title to confirm",
            key=f"cls_del_confirm_{class_id}",
            placeholder=classroom["title"],
        )
        if st.button(
            "Delete class permanently",
            key=f"cls_del_{class_id}",
            type="primary",
        ):
            if (confirm_title or "").strip() != classroom["title"]:
                st.error("Title did not match — class was not deleted.")
            else:
                try:
                    delete_class(token, class_id)
                    st.session_state.pop("managed_class_id", None)
                    st.session_state.pop("cls_manage_pick", None)
                    clear_widget_keys(f"cls_del_confirm_{class_id}")
                    clear_widget_keys(f"cls_title_{class_id}")
                    clear_widget_keys(f"cls_desc_{class_id}")
                    clear_widget_keys(f"cls_vis_{class_id}")
                    clear_widget_keys(f"cls_active_{class_id}")
                    st.session_state["cls_flash"] = (
                        f"Class **{classroom['title']}** deleted."
                    )
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

    # ------------------------------------------------------------------ #
    # Quizzes — list + create + import; edit opens a dialog
    # ------------------------------------------------------------------ #
    @st.dialog("Edit quiz", width="large")
    def edit_quiz_dialog(quiz_id: int) -> None:
        quiz = id_to_quiz.get(quiz_id)
        if not quiz:
            st.error("Quiz not found.")
            if st.button("Close"):
                st.session_state.pop(f"editing_quiz_{class_id}", None)
                st.rerun()
            return

        st.markdown(f"### {quiz['title']}")
        order_key = f"quiz_order_{quiz_id}"
        server_ids = list(quiz.get("question_ids") or [])
        server_snap = f"quiz_server_{quiz_id}"
        if (
            order_key not in st.session_state
            or st.session_state.get(server_snap) != server_ids
        ):
            st.session_state[order_key] = list(server_ids)
            st.session_state[server_snap] = list(server_ids)
        order = list(st.session_state[order_key])
        unsaved_changes_banner(
            order != list(st.session_state.get(server_snap, server_ids)),
            message="Question list changed — Save question list before closing.",
        )

        timed = st.checkbox(
            "Timed quiz",
            value=quiz["is_timed"],
            key=f"dlg_timed_{quiz_id}",
        )
        duration_val = st.number_input(
            "Duration (seconds)",
            min_value=30,
            value=int(quiz["duration_seconds"] or 120),
            key=f"dlg_dur_{quiz_id}",
        )
        if st.button("Save quiz settings", key=f"dlg_qset_{quiz_id}"):
            try:
                update_quiz(
                    token,
                    quiz_id,
                    {
                        "is_timed": timed,
                        "duration_seconds": int(duration_val) if timed else None,
                    },
                )
                success_banner("Quiz settings saved.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

        st.markdown("#### Questions in this quiz")
        if not order:
            st.info("No questions yet — create one below or import from the bank.")
        for index, qid in enumerate(order):
            question = id_to_question.get(qid)
            header = (
                question_summary_label(question)
                if question
                else f"#{qid} · (missing)"
            )
            cols = st.columns([8, 1, 1, 1])
            with cols[0]:
                with st.expander(f"{index + 1}. {header}", expanded=False):
                    if question:
                        render_question_preview(question, show_answers=True)
                        if question.get("can_edit", question.get("can_delete")):
                            render_question_edit_form(
                                token,
                                question,
                                subjects_tree=subjects_tree,
                                key_prefix=f"dlg_eq_{quiz_id}_{qid}",
                            )
            if cols[1].button(
                "↑", key=f"dlg_qq_up_{quiz_id}_{qid}", disabled=index == 0
            ):
                order[index - 1], order[index] = order[index], order[index - 1]
                st.session_state[order_key] = order
                st.rerun()
            if cols[2].button(
                "↓",
                key=f"dlg_qq_dn_{quiz_id}_{qid}",
                disabled=index >= len(order) - 1,
            ):
                order[index + 1], order[index] = order[index], order[index + 1]
                st.session_state[order_key] = order
                st.rerun()
            if cols[3].button("✕", key=f"dlg_qq_rm_{quiz_id}_{qid}"):
                order.pop(index)
                st.session_state[order_key] = order
                st.rerun()

        if st.button(
            "Save question list",
            type="primary",
            key=f"dlg_qsave_{quiz_id}",
        ):
            try:
                set_quiz_questions(token, quiz_id, order)
                st.session_state[server_snap] = list(order)
                success_banner("Quiz questions saved.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

        st.divider()
        st.markdown("#### Create new question")
        ntype = st.selectbox(
            "Type", ["mcq", "coding"], key=f"dlg_ntype_{quiz_id}"
        )
        ntitle = st.text_input("Title", key=f"dlg_ntitle_{quiz_id}")
        ndesc = st.text_area(
            "Description (optional)",
            key=f"dlg_ndesc_{quiz_id}",
            height=100,
        )
        nsubject, nareas = subject_area_picker(
            subjects_tree=subjects_tree,
            key_prefix=f"dlg_nquiz_{quiz_id}",
        )
        nchoices: list[str] = []
        ncorrect: str | None = None
        if ntype == "mcq":
            nchoices, ncorrect = mcq_choices_editor(f"dlg_nmcq_{quiz_id}")
            ncases: list[dict] = []
            ncode = ""
        else:
            ncode = st.text_area(
                "Starter code",
                value='print("ok")\n',
                key=f"dlg_ncode_{quiz_id}",
            )
            ncases = test_case_editor(f"dlg_nquiz_cases_{quiz_id}")
        if st.button(
            "Create & add question",
            type="primary",
            key=f"dlg_attach_q_{quiz_id}",
        ):
            if len((ntitle or "").strip()) < 3:
                st.error("Title needs at least 3 characters.")
            elif not nareas:
                st.error("Choose at least one area.")
            else:
                payload = {
                    "title": ntitle.strip(),
                    "description": ndesc or "",
                    "type": ntype,
                    "difficulty": "easy",
                    "subject": nsubject,
                    "topics": nareas,
                    "language": "python",
                    "visibility": "private",
                }
                try:
                    if ntype == "mcq":
                        if len(nchoices) < 2 or not ncorrect:
                            st.error("Add at least two options and pick the answer.")
                            st.stop()
                        payload["choices"] = nchoices
                        payload["correct_answer"] = ncorrect
                    else:
                        if not ncases:
                            st.error("Add at least one test case.")
                            st.stop()
                        payload["starter_code"] = ncode
                        payload["test_cases"] = ncases
                    created_q = create_question(token, payload)
                    new_order = list(st.session_state.get(order_key, server_ids))
                    if created_q["id"] not in new_order:
                        new_order.append(created_q["id"])
                    set_quiz_questions(token, quiz_id, new_order)
                    st.session_state[order_key] = new_order
                    st.session_state[server_snap] = list(new_order)
                    success_banner("Question created and added to the quiz.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

        import_key = f"dlg_import_q_{quiz_id}"
        if st.button(
            "Import global questions",
            key=f"dlg_toggle_import_{quiz_id}",
        ):
            st.session_state[import_key] = not st.session_state.get(import_key, False)
            st.rerun()

        if st.session_state.get(import_key):
            st.markdown("##### Import from Global Question Bank")
            available_q = [q for q in bank if q["id"] not in set(order)]
            filtered = bank_picker_filters(
                available_q,
                key_prefix=f"dlg_quiz_bank_{class_id}_{quiz_id}",
                allow_type_filter=True,
            )
            for question in filtered[:25]:
                with st.expander(question_summary_label(question), expanded=False):
                    render_question_preview(question, show_answers=True)
                    b1, b2 = st.columns(2)
                    if b1.button(
                        "Add as-is",
                        key=f"dlg_qadd_{quiz_id}_{question['id']}",
                    ):
                        order.append(question["id"])
                        st.session_state[order_key] = order
                        st.rerun()
                    if b2.button(
                        "Customize (private copy)",
                        key=f"dlg_qclone_{quiz_id}_{question['id']}",
                        type="primary",
                    ):
                        try:
                            copy = clone_question(token, question["id"])
                            order.append(copy["id"])
                            st.session_state[order_key] = order
                            success_banner("Private copy added — save the question list.")
                            st.rerun()
                        except APIError as error:
                            st.error(str(error))

        st.divider()
        d1, d2 = st.columns(2)
        if d1.button("Close", key=f"dlg_close_{quiz_id}"):
            st.session_state.pop(f"editing_quiz_{class_id}", None)
            st.session_state.pop(import_key, None)
            st.rerun()
        if d2.button("Delete this quiz", key=f"dlg_del_{quiz_id}"):
            try:
                published = list(classroom.get("quiz_ids") or [])
                remaining = [qid for qid in published if qid != quiz_id]
                set_class_quizzes(token, class_id, remaining)
                delete_quiz(token, quiz_id)
                st.session_state.pop(f"editing_quiz_{class_id}", None)
                draft_key = f"cls_quiz_draft_{class_id}"
                snap_key = f"cls_quiz_snap_{class_id}"
                st.session_state[draft_key] = remaining
                st.session_state[snap_key] = list(remaining)
                success_banner("Quiz deleted.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

    with quizzes_tab:
        published_ids = list(classroom.get("quiz_ids") or [])
        draft_key = f"cls_quiz_draft_{class_id}"
        snap_key = f"cls_quiz_snap_{class_id}"
        if (
            draft_key not in st.session_state
            or st.session_state.get(snap_key) != published_ids
        ):
            st.session_state[draft_key] = list(published_ids)
            st.session_state[snap_key] = list(published_ids)
        draft_ids = list(st.session_state[draft_key])
        quizzes_dirty = draft_ids != list(st.session_state.get(snap_key, published_ids))
        unsaved_changes_banner(
            quizzes_dirty,
            message="Quiz list draft changed — press Save published quizzes to keep it.",
        )

        editing_id = st.session_state.get(f"editing_quiz_{class_id}")
        if editing_id:
            edit_quiz_dialog(int(editing_id))

        st.markdown("#### Create new quiz")
        with st.form(f"create_quiz_{class_id}"):
            qtitle = st.text_input("Quiz title")
            qdesc = st.text_area("Description (optional)", height=80)
            qvis = st.selectbox(
                "Sharing",
                ["private", "public"],
                format_func=lambda value: (
                    "Private — only this class / you"
                    if value == "private"
                    else "Shared — listed in Global Quiz Bank"
                ),
            )
            qtimed = st.checkbox("Timed quiz")
            qdur = st.number_input(
                "Duration (seconds)", min_value=30, value=120, step=30
            )
            qsubmit = st.form_submit_button("Create & publish", type="primary")
        if qsubmit:
            if len((qtitle or "").strip()) < 3:
                st.error("Quiz title needs at least 3 characters.")
            else:
                try:
                    created = create_quiz(
                        token,
                        {
                            "title": qtitle.strip(),
                            "description": qdesc or "",
                            "is_timed": qtimed,
                            "duration_seconds": int(qdur) if qtimed else None,
                            "visibility": qvis,
                        },
                    )
                    new_ids = list(st.session_state.get(draft_key, published_ids))
                    if created["id"] not in new_ids:
                        new_ids.append(created["id"])
                    set_class_quizzes(token, class_id, new_ids)
                    st.session_state[draft_key] = new_ids
                    st.session_state[snap_key] = list(new_ids)
                    st.session_state[f"editing_quiz_{class_id}"] = created["id"]
                    success_banner("Quiz created — edit it in the popup.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

        import_quiz_key = f"show_import_quiz_{class_id}"
        if st.button(
            "Import global quiz",
            key=f"toggle_import_quiz_{class_id}",
        ):
            st.session_state[import_quiz_key] = not st.session_state.get(
                import_quiz_key, False
            )
            st.rerun()

        if st.session_state.get(import_quiz_key):
            st.markdown("##### Import from Global Quiz Bank")
            st.caption(
                "Import creates a private class copy. "
                "Your own quizzes can be reused without copying."
            )
            bank_quizzes = [
                q
                for q in all_quizzes
                if q.get("visibility") == "public" or q.get("owner_id") == teacher_id
            ]
            available = [q for q in bank_quizzes if q["id"] not in set(draft_ids)]
            attach_search = st.text_input(
                "Search quizzes",
                key=f"attach_q_search_{class_id}",
                placeholder="Filter by title or description",
            )
            needle = attach_search.strip().lower()
            if needle:
                available = [
                    q
                    for q in available
                    if needle in (q.get("title") or "").lower()
                    or needle in (q.get("description") or "").lower()
                ]
            if not available:
                st.info("No quizzes to import.")
            for quiz in available[:20]:
                sharing = (
                    "Shared" if quiz.get("visibility") == "public" else "Private"
                )
                own = quiz.get("owner_id") == teacher_id
                with st.expander(
                    f"{quiz['title']} · {sharing} · "
                    f"{len(quiz.get('question_ids') or [])} questions · "
                    f"{'Timed' if quiz.get('is_timed') else 'Untimed'}"
                ):
                    render_preserved_text(quiz.get("description") or "")
                    c1, c2 = st.columns(2)
                    if c1.button(
                        "Import copy",
                        key=f"import_copy_{class_id}_{quiz['id']}",
                        type="primary",
                    ):
                        try:
                            copy = clone_quiz(token, quiz["id"])
                            new_ids = list(
                                st.session_state.get(draft_key, published_ids)
                            )
                            new_ids.append(copy["id"])
                            set_class_quizzes(token, class_id, new_ids)
                            st.session_state[draft_key] = new_ids
                            st.session_state[snap_key] = list(new_ids)
                            st.session_state[f"editing_quiz_{class_id}"] = copy["id"]
                            st.session_state[import_quiz_key] = False
                            success_banner("Imported — edit the copy in the popup.")
                            st.rerun()
                        except APIError as error:
                            st.error(str(error))
                    if own and c2.button(
                        "Use my existing",
                        key=f"use_own_{class_id}_{quiz['id']}",
                    ):
                        draft_ids.append(quiz["id"])
                        st.session_state[draft_key] = draft_ids
                        st.rerun()

        st.divider()
        st.markdown("#### Quizzes in this class")
        st.caption(
            "Published list = visible to students. Remove a quiz (✕) to hide it, "
            "then Save."
        )
        if not draft_ids:
            st.info("No quizzes yet — create one above or import a global quiz.")
        for index, quiz_id in enumerate(draft_ids):
            quiz = id_to_quiz.get(quiz_id)
            cols = st.columns([7, 1.2, 1, 1, 1])
            with cols[0]:
                if quiz:
                    sharing = (
                        "Shared"
                        if quiz.get("visibility") == "public"
                        else "Private"
                    )
                    st.markdown(
                        f"**{index + 1}. {quiz['title']}**  \n"
                        f"{sharing} · "
                        f"{'Timed' if quiz.get('is_timed') else 'Untimed'} · "
                        f"{len(quiz.get('question_ids') or [])} questions"
                    )
                else:
                    st.warning(f"Quiz #{quiz_id} missing from catalog.")
            if cols[1].button(
                "Edit",
                key=f"edit_quiz_{class_id}_{quiz_id}",
                type="primary",
                disabled=quiz is None,
            ):
                st.session_state[f"editing_quiz_{class_id}"] = quiz_id
                st.rerun()
            if cols[2].button(
                "↑", key=f"qup_{class_id}_{quiz_id}", disabled=index == 0
            ):
                draft_ids[index - 1], draft_ids[index] = (
                    draft_ids[index],
                    draft_ids[index - 1],
                )
                st.session_state[draft_key] = draft_ids
                st.rerun()
            if cols[3].button(
                "↓",
                key=f"qdn_{class_id}_{quiz_id}",
                disabled=index >= len(draft_ids) - 1,
            ):
                draft_ids[index + 1], draft_ids[index] = (
                    draft_ids[index],
                    draft_ids[index + 1],
                )
                st.session_state[draft_key] = draft_ids
                st.rerun()
            if cols[4].button("✕", key=f"qrm_{class_id}_{quiz_id}"):
                draft_ids.pop(index)
                st.session_state[draft_key] = draft_ids
                st.rerun()

        if st.button(
            "Save published quizzes",
            type="primary",
            key=f"save_q_{class_id}",
        ):
            try:
                set_class_quizzes(token, class_id, draft_ids)
                st.session_state[snap_key] = list(draft_ids)
                success_banner("Class quizzes saved.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

    # ------------------------------------------------------------------ #
    # Modules
    # ------------------------------------------------------------------ #
    with modules_tab:
        if st.session_state.pop("_goto_module_editor", None):
            st.switch_page("pages/_ModuleEditor.py")

        try:
            modules = sorted(
                list_admin_modules(token, class_id=class_id),
                key=lambda item: (item.get("position", 0), item.get("id", 0)),
            )
        except APIError as error:
            st.error(str(error))
            modules = []

        st.markdown("#### Create new module")
        st.caption(
            "A module is a topic students open from the module hub. "
            "Inside the editor, add Page markers to split subtopics."
        )
        with st.form(f"new_module_{class_id}", clear_on_submit=True):
            mtitle = st.text_input(
                "Title",
                placeholder="Module 01 — Basics (min. 3 characters)",
            )
            mlabel = st.text_input("Label", value="Beginner")
            mcreate = st.form_submit_button("Add module", type="primary")
        if mcreate:
            clean_title = (mtitle or "").strip()
            if len(clean_title) < 3:
                st.error("Module title needs at least 3 characters.")
            else:
                try:
                    created = create_module(
                        token,
                        {
                            "class_id": class_id,
                            "title": clean_title,
                            "description": "",
                            "position": len(modules),
                            "difficulty_label": (mlabel or "").strip() or None,
                        },
                    )
                    st.session_state["editor_module_id"] = created["id"]
                    st.session_state["managed_class_id"] = class_id
                    st.session_state["_goto_module_editor"] = True
                    success_banner("Module created — opening editor.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

        st.divider()
        st.markdown("#### Modules in this class")
        st.caption(
            "Ordered topics for the student module hub. Edit to add pages, "
            "reading, media, and practice."
        )
        if not modules:
            st.info("No modules yet — create one above.")
        for index, module in enumerate(modules):
            block_count = len(module.get("blocks") or [])
            practice_count = sum(
                1
                for block in (module.get("blocks") or [])
                if block.get("type") in ("mcq", "coding")
            )
            cols = st.columns([7, 1.2, 1, 1, 1])
            with cols[0]:
                st.markdown(
                    f"**{module['position'] + 1}. {module['title']}**  \n"
                    f"{module.get('difficulty_label') or 'Chapter'} · "
                    f"{block_count} section(s) · {practice_count} practice"
                )
            if cols[1].button(
                "Edit",
                key=f"open_mod_{class_id}_{module['id']}",
                type="primary",
            ):
                st.session_state["editor_module_id"] = module["id"]
                st.session_state["managed_class_id"] = class_id
                st.switch_page("pages/_ModuleEditor.py")
            if cols[2].button(
                "↑",
                key=f"mod_up_{class_id}_{module['id']}",
                disabled=index == 0,
            ):
                order = [m["id"] for m in modules]
                order[index - 1], order[index] = order[index], order[index - 1]
                try:
                    set_class_modules(token, class_id, order)
                    st.rerun()
                except APIError as error:
                    st.error(str(error))
            if cols[3].button(
                "↓",
                key=f"mod_dn_{class_id}_{module['id']}",
                disabled=index >= len(modules) - 1,
            ):
                order = [m["id"] for m in modules]
                order[index + 1], order[index] = order[index], order[index + 1]
                try:
                    set_class_modules(token, class_id, order)
                    st.rerun()
                except APIError as error:
                    st.error(str(error))
            if cols[4].button("✕", key=f"mod_rm_{class_id}_{module['id']}"):
                try:
                    delete_module(token, module["id"])
                    success_banner("Module deleted.")
                    st.rerun()
                except APIError as error:
                    st.error(str(error))

    # ------------------------------------------------------------------ #
    # Question bank
    # ------------------------------------------------------------------ #
    with bank_tab:
        render_question_bank_panel(
            token,
            subjects_tree,
            key_prefix=f"cls_qb_{class_id}",
        )

    # ------------------------------------------------------------------ #
    # Announcements + performance
    # ------------------------------------------------------------------ #
    with announcements:
        with st.form(f"announce_{class_id}"):
            a_title = st.text_input("Title", placeholder="This week's focus")
            a_body = st.text_area("Message", height=120)
            posted = st.form_submit_button("Post announcement", type="primary")
        if posted:
            try:
                create_class_announcement(token, class_id, a_title, a_body)
                success_banner("Announcement posted.")
                st.rerun()
            except APIError as error:
                st.error(str(error))

        try:
            notes = list_class_announcements(token, class_id)
        except APIError as error:
            st.error(str(error))
            notes = []
        if not notes:
            st.info("No announcements yet.")
        for note in notes:
            with st.container(border=True):
                st.markdown(f"**{note['title']}**")
                render_preserved_text(note.get("body") or "")
                st.caption(
                    f"{note.get('author_username', '')} · "
                    f"{str(note.get('created_at', ''))[:19].replace('T', ' ')}"
                )
                if st.button("Delete", key=f"adel_{note['id']}"):
                    try:
                        delete_class_announcement(token, class_id, note["id"])
                        success_banner("Announcement removed.")
                        st.rerun()
                    except APIError as error:
                        st.error(str(error))

    with performance:
        try:
            rows = get_class_performance(token, class_id)
        except APIError as error:
            st.error(str(error))
            rows = []
        if not rows:
            st.info("No performance data yet.")
        else:
            st.dataframe(
                [
                    {
                        "student": row["username"],
                        "quizzes": (
                            f"{row['quizzes_completed']}/"
                            f"{row['quizzes_published']}"
                        ),
                        "avg best score": row.get("average_best_score"),
                        "coding levels": (
                            f"{row['coding_levels_passed']}/"
                            f"{row['coding_levels_total']}"
                        ),
                    }
                    for row in rows
                ],
                width="stretch",
                hide_index=True,
            )
