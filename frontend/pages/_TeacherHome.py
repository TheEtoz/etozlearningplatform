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
    f"Signed in as {user.get('username')}. Use the sidebar to move between tools, "
    "or jump in below."
)

c1, c2, c3 = st.columns(3, gap="large")
with c1:
    with st.container(border=True):
        st.subheader("1. Question Bank")
        st.write(
            "Create MCQ/coding items, tag topic areas, and define coding tests "
            "with simple input/output cases."
        )
        st.page_link("pages/_QuestionBank.py", label="Open question bank", icon="📚")
with c2:
    with st.container(border=True):
        st.subheader("2. Quizzes")
        st.write(
            "Build timed or untimed quizzes. Import bank questions or create new "
            "ones that also join the bank."
        )
        st.page_link("pages/_QuizManager.py", label="Open quiz manager", icon="📝")
with c3:
    with st.container(border=True):
        st.subheader("3. Coding Path")
        st.write(
            "Design the learning path as lecture chapters (modules) with ordered "
            "coding levels."
        )
        st.page_link("pages/_PathManager.py", label="Open path designer", icon="🗺️")

st.info(
    "Tip: students never see these pages. After you save, forms clear and a "
    "success notice appears."
)
