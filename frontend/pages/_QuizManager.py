"""Legacy redirect — quizzes are managed inside Classes."""

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

from frontend.utils.guards import require_teacher
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Quizzes | ETOZ", page_icon="📝", layout="centered")
init_session_state()
require_teacher()
st.info("Quizzes are managed inside each class.")
st.switch_page("pages/_ClassManager.py")
