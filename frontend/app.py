"""ETOZ marketing home — no role UI until the visitor logs in."""

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

from frontend.utils.guards import hub_for_role
from frontend.utils.nav import render_public_sidebar, render_nav_for_current_user
from frontend.utils.session import init_session_state, is_logged_in

st.set_page_config(
    page_title="ETOZ Learning Platform",
    page_icon="🐍",
    layout="wide",
)

init_session_state()

if is_logged_in():
    render_nav_for_current_user()
    user = st.session_state.current_user or {}
    st.switch_page(hub_for_role(user.get("role")))

render_public_sidebar()

st.markdown(
    """
    <style>
    .etoz-hero {
        min-height: 70vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 2.5rem 1rem 3rem;
        background:
            radial-gradient(circle at 15% 20%, rgba(14, 116, 144, 0.18), transparent 40%),
            radial-gradient(circle at 85% 10%, rgba(34, 197, 94, 0.12), transparent 35%),
            linear-gradient(180deg, #f7fafc 0%, #eef5f3 55%, #f8fafc 100%);
        border-radius: 1rem;
    }
    .etoz-brand {
        font-family: "Segoe UI", "Trebuchet MS", sans-serif;
        font-size: clamp(3rem, 8vw, 5.5rem);
        font-weight: 800;
        letter-spacing: -0.04em;
        color: #0f172a;
        margin: 0;
        line-height: 1;
    }
    .etoz-tag {
        margin-top: 1rem;
        max-width: 34rem;
        font-size: 1.15rem;
        color: #334155;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="etoz-hero">
      <p class="etoz-brand">ETOZ</p>
      <p class="etoz-tag">
        Learn Python through quizzes and a guided coding path.
        Sign in to continue as a student or teacher.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right, _ = st.columns([1, 1, 2])
with left:
    st.page_link("pages/Login.py", label="Log in", icon="🔐")
with right:
    st.page_link("pages/Register.py", label="Create account", icon="📝")
