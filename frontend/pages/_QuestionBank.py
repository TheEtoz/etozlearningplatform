"""Teacher question bank — create, browse, and edit questions."""

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

from frontend.utils.api import APIError, list_subjects
from frontend.utils.guards import require_teacher
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.teacher_panels import render_question_bank_panel

st.set_page_config(page_title="Question Bank | ETOZ", page_icon="📚", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

st.title("Question bank")
st.page_link("pages/_ClassManager.py", label="← Classes", icon="🏫")

try:
    subjects_tree = list_subjects(token)
except APIError as error:
    st.error(str(error))
    st.stop()

render_question_bank_panel(token, subjects_tree, key_prefix="qb_page")
