"""Teacher coding-path designer — modules as lecture sections with ordered levels."""

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
    create_module,
    delete_module,
    list_admin_modules,
    list_admin_questions,
    set_module_levels,
    update_module,
)
from frontend.utils.guards import require_teacher
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.ui import (
    bank_picker_filters,
    question_summary_label,
    render_preserved_text,
    render_question_preview,
    success_banner,
)

st.set_page_config(page_title="Path Manager | ETOZ", page_icon="🗺️", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

st.title("Coding Path Designer")
st.caption(
    "Think of each module as a lecture chapter. Order modules top-to-bottom, "
    "then place coding levels inside each chapter. Students can open any level freely."
)

try:
    modules = sorted(
        list_admin_modules(token),
        key=lambda item: (item.get("position", 0), item.get("id", 0)),
    )
    bank = [q for q in list_admin_questions(token) if q.get("type") == "coding"]
except APIError as error:
    st.error(str(error))
    st.stop()

id_to_question = {q["id"]: q for q in bank}

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader("Path outline")
    if not modules:
        st.info("No modules yet — create the first chapter on the right.")
    for module in modules:
        level_count = len(module.get("question_ids") or [])
        st.markdown(
            f"**{module['position'] + 1}. {module['title']}**  \n"
            f"{module.get('difficulty_label') or 'Chapter'} · {level_count} level(s)"
        )
    st.divider()
    with st.form("new_module_form"):
        st.markdown("#### New chapter / module")
        title = st.text_input("Title", placeholder="Module 1 - Basics")
        description = st.text_area(
            "Lecture description",
            height=100,
            placeholder="What students learn in this chapter...",
        )
        position = st.number_input(
            "Order (0 = first)",
            min_value=0,
            value=len(modules),
        )
        label = st.text_input("Label", value="Beginner")
        created = st.form_submit_button("Add module", type="primary")
    if created:
        try:
            create_module(
                token,
                {
                    "title": title,
                    "description": description,
                    "position": int(position),
                    "difficulty_label": label or None,
                },
            )
            success_banner("Module added to the path.")
            st.rerun()
        except APIError as error:
            st.error(str(error))

with right:
    st.subheader("Design a module")
    if not modules:
        st.stop()

    choice = st.selectbox(
        "Module to edit",
        options=[f"#{m['id']} · {m['title']}" for m in modules],
    )
    module = next(m for m in modules if f"#{m['id']} · {m['title']}" == choice)

    with st.form(f"edit_module_{module['id']}"):
        new_title = st.text_input("Title", value=module["title"])
        new_desc = st.text_area(
            "Lecture description",
            value=module.get("description") or "",
            height=120,
        )
        new_pos = st.number_input(
            "Order",
            min_value=0,
            value=int(module["position"]),
        )
        new_label = st.text_input(
            "Difficulty label",
            value=module.get("difficulty_label") or "",
        )
        save_meta = st.form_submit_button("Save module details", type="primary")
    if save_meta:
        try:
            update_module(
                token,
                module["id"],
                {
                    "title": new_title,
                    "description": new_desc,
                    "position": int(new_pos),
                    "difficulty_label": new_label or None,
                },
            )
            success_banner("Module details saved.")
            st.rerun()
        except APIError as error:
            st.error(str(error))

    st.markdown("#### Levels in this chapter")
    st.caption("Open a level to read the prompt and tests. Reorder with ↑ ↓ or remove with ✕.")

    current_ids = list(module.get("question_ids") or [])
    order_key = f"path_order_{module['id']}"
    server_snap_key = f"path_server_{module['id']}"
    if (
        order_key not in st.session_state
        or st.session_state.get(server_snap_key) != current_ids
    ):
        st.session_state[order_key] = list(current_ids)
        st.session_state[server_snap_key] = list(current_ids)
    order = list(st.session_state[order_key])

    if not order:
        st.info("No levels yet — add a coding question from the bank below.")

    for index, qid in enumerate(order):
        question = id_to_question.get(qid)
        header = (
            question_summary_label(question)
            if question
            else f"#{qid} · (missing from bank)"
        )
        cols = st.columns([8, 1, 1, 1])
        with cols[0]:
            with st.expander(f"Level {index + 1}. {header}", expanded=False):
                if question:
                    render_question_preview(question, show_answers=True)
                else:
                    st.warning("Question not found in the coding bank.")
        if cols[1].button("↑", key=f"up_{module['id']}_{qid}", disabled=index == 0):
            order[index - 1], order[index] = order[index], order[index - 1]
            st.session_state[order_key] = order
            st.rerun()
        if cols[2].button(
            "↓",
            key=f"down_{module['id']}_{qid}",
            disabled=index >= len(order) - 1,
        ):
            order[index + 1], order[index] = order[index], order[index + 1]
            st.session_state[order_key] = order
            st.rerun()
        if cols[3].button("✕", key=f"rm_{module['id']}_{qid}"):
            order.pop(index)
            st.session_state[order_key] = order
            st.rerun()

    if st.button("Save level order to path", type="primary"):
        try:
            set_module_levels(token, module["id"], order)
            st.session_state[server_snap_key] = list(order)
            success_banner("Coding path chapter updated.")
            st.rerun()
        except APIError as error:
            st.error(str(error))

    st.divider()
    st.markdown("#### Add coding question from bank")
    available = [q for q in bank if q["id"] not in set(order)]
    filtered = bank_picker_filters(
        available,
        key_prefix=f"path_bank_{module['id']}",
        allow_type_filter=False,
    )
    if not filtered:
        st.info("No matching coding questions left to add.")
    else:
        preview_limit = 25
        for question in filtered[:preview_limit]:
            with st.expander(question_summary_label(question), expanded=False):
                render_question_preview(question, show_answers=True)
                if st.button(
                    "Add as level",
                    key=f"add_level_{module['id']}_{question['id']}",
                    type="primary",
                ):
                    order.append(question["id"])
                    st.session_state[order_key] = order
                    st.rerun()
        if len(filtered) > preview_limit:
            st.caption(
                f"Showing first {preview_limit} matches — refine search to narrow further."
            )

    st.divider()
    with st.expander("Preview lecture text"):
        render_preserved_text(module.get("description") or "")

    if st.button("Delete this module"):
        try:
            delete_module(token, module["id"])
            success_banner("Module deleted.")
            st.rerun()
        except APIError as error:
            st.error(str(error))
