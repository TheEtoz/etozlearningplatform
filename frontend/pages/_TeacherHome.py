"""Teacher hub after login."""

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

st.set_page_config(page_title="Teacher Home | ETOZ", page_icon="🛠️", layout="wide")
init_session_state()
user = require_teacher()

st.title("Teacher Home")
st.caption(
    f"Signed in as {user.get('username')}. "
    "Classes hold quizzes, question bank, modules, and lectures."
)

with st.container(border=True):
    st.subheader("Classes")
    st.write(
        "Create classes, build quizzes, import bank questions, write module lectures "
        "(Markdown/LaTeX), add coding levels, post announcements, and review performance."
    )
    st.page_link("pages/_ClassManager.py", label="Open classes", icon="🏫")
