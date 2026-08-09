"""Student class home — announcements, quizzes, and lectures."""

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

from frontend.utils.api import APIError, get_class, get_demo_class, list_class_announcements
from frontend.utils.guards import require_student
from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import get_access_token, init_session_state, is_logged_in
from frontend.utils.ui import render_preserved_text

st.set_page_config(page_title="Class Home | ETOZ", page_icon="🏫", layout="wide")
init_session_state()
require_student()

class_id = st.session_state.get("active_class_id")
if not class_id and is_public_mode() and not is_logged_in():
    try:
        demo = get_demo_class()
        st.session_state.active_class_id = demo["id"]
        st.session_state.active_class_title = demo["title"]
        class_id = demo["id"]
    except APIError:
        class_id = None

if not class_id:
    st.warning("Pick a class first.")
    st.page_link("pages/Classes.py", label="Go to Classes", icon="🏫")
    st.stop()

token = get_access_token()
try:
    classroom = get_class(token, class_id)
except APIError as error:
    st.error(str(error))
    st.page_link("pages/Classes.py", label="Back to Classes", icon="🏫")
    st.stop()

st.session_state.active_class_title = classroom["title"]
st.title(classroom["title"])
render_preserved_text(classroom.get("description") or "")
st.caption(
    f"{classroom.get('quiz_count', 0)} quizzes · "
    f"{classroom.get('module_count', 0)} modules"
)
st.page_link("pages/Classes.py", label="All classes", icon="🏫")

try:
    notes = list_class_announcements(token, class_id)
except APIError:
    notes = []

if notes:
    st.subheader("Announcements")
    for note in notes[:5]:
        with st.container(border=True):
            st.markdown(f"**{note['title']}**")
            render_preserved_text(note.get("body") or "")
            st.caption(
                str(note.get("created_at", ""))[:19].replace("T", " ")
            )


def _modules_card() -> None:
    with st.container(border=True):
        st.subheader("Modules")
        st.write("Topics with numbered modules — open Learn, then read subsections.")
        st.page_link("pages/Modules.py", label="Open Modules", icon="📘")


def _quizzes_card() -> None:
    with st.container(border=True):
        st.subheader("Quizzes")
        st.write("Class assessments and practice quizzes.")
        st.page_link("pages/Practice.py", label="Open Quizzes", icon="🧠")


left, right = st.columns(2, gap="large")
with left:
    _modules_card()
with right:
    _quizzes_card()
