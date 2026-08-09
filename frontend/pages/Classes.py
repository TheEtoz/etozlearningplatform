"""Browse / open classes — public demo skips enrollment."""

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

import importlib
import frontend.utils.reload as _etoz_reload
importlib.reload(_etoz_reload)
_etoz_reload.reload_frontend_utils()

from frontend.utils.api import (
    APIError,
    enroll_in_class,
    list_enrolled_classes,
    list_public_classes,
)
from frontend.utils.guards import require_student
from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import get_access_token, init_session_state, is_logged_in
from frontend.utils.ui import render_preserved_text, success_banner

st.set_page_config(page_title="Classes | ETOZ", page_icon="🏫", layout="wide")
init_session_state()
require_student()
token = get_access_token()

st.title("Classes")

# Anonymous visitors: open public classes without enrolling.
if is_public_mode() and not is_logged_in():
    st.caption("Open any public class as a guest, or log in to enroll and save progress.")
    try:
        public = list_public_classes()
    except APIError as error:
        st.error(str(error))
        public = []

    if not public:
        st.info("No open public classes right now.")
    for classroom in public:
        with st.container(border=True):
            st.subheader(classroom["title"])
            render_preserved_text(classroom.get("description") or "")
            st.caption(
                f"Teacher: {classroom.get('owner_username', '—')} · "
                f"{classroom.get('quiz_count', 0)} quizzes · "
                f"{classroom.get('module_count', 0)} modules"
            )
            if st.button(
                "Open class",
                key=f"open_public_{classroom['id']}",
                type="primary",
            ):
                st.session_state.active_class_id = classroom["id"]
                st.session_state.active_class_title = classroom["title"]
                st.switch_page("pages/ClassHome.py")
    st.page_link("pages/Login.py", label="Log in", icon="🔐")
    st.page_link("pages/Register.py", label="Create account", icon="📝")
    st.stop()

st.caption(
    "Enroll in a subject/class to access its quizzes and lectures. "
    "Private classes need an enrollment code from your teacher."
)

my_tab, browse_tab, code_tab = st.tabs(
    ["My classes", "Browse public", "Join with code"]
)

with my_tab:
    try:
        enrolled = list_enrolled_classes(token)
    except APIError as error:
        st.error(str(error))
        enrolled = []

    if not enrolled:
        st.info("You are not enrolled in any class yet.")
    for classroom in enrolled:
        with st.container(border=True):
            st.subheader(classroom["title"])
            render_preserved_text(classroom.get("description") or "")
            st.caption(
                f"{classroom.get('quiz_count', 0)} quizzes · "
                f"{classroom.get('module_count', 0)} coding modules"
            )
            if st.button(
                "Open class",
                key=f"open_{classroom['id']}",
                type="primary",
            ):
                st.session_state.active_class_id = classroom["id"]
                st.session_state.active_class_title = classroom["title"]
                st.switch_page("pages/ClassHome.py")

with browse_tab:
    try:
        public = list_public_classes(token)
    except APIError as error:
        st.error(str(error))
        public = []

    if not public:
        st.info("No open public classes right now.")
    for classroom in public:
        with st.container(border=True):
            st.subheader(classroom["title"])
            render_preserved_text(classroom.get("description") or "")
            st.caption(
                f"Teacher: {classroom.get('owner_username', '—')} · "
                f"{classroom.get('quiz_count', 0)} quizzes · "
                f"{classroom.get('module_count', 0)} modules"
            )
            if st.button("Enroll", key=f"enroll_{classroom['id']}", type="primary"):
                try:
                    joined = enroll_in_class(token, class_id=classroom["id"])
                    st.session_state.active_class_id = joined["id"]
                    st.session_state.active_class_title = joined["title"]
                    success_banner(f"Enrolled in {joined['title']}.")
                    st.switch_page("pages/ClassHome.py")
                except APIError as error:
                    st.error(str(error))

with code_tab:
    code = st.text_input(
        "Enrollment code",
        placeholder="e.g. AB12CD34",
        help="Ask your teacher for the class code.",
    )
    if st.button("Join class", type="primary"):
        if not code.strip():
            st.error("Enter an enrollment code.")
        else:
            try:
                joined = enroll_in_class(token, code=code.strip())
                st.session_state.active_class_id = joined["id"]
                st.session_state.active_class_title = joined["title"]
                success_banner(f"Joined {joined['title']}.")
                st.switch_page("pages/ClassHome.py")
            except APIError as error:
                st.error(str(error))
