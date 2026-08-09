"""Role-scoped navigation — hides Streamlit's default multipage list."""

from __future__ import annotations

import streamlit as st

from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import clear_auth_session, init_session_state, is_logged_in


def hide_default_sidebar_pages() -> None:
    """Hide Streamlit's auto page list so roles never see each other's pages."""

    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"],
        div[data-testid="stSidebarNavItems"],
        ul[data-testid="stSidebarNavItems"],
        nav[data-testid="stSidebarNav"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            max-height: 0 !important;
            overflow: hidden !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        section[data-testid="stSidebar"] { min-width: 15rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_student_sidebar() -> None:
    """Student-only navigation links."""

    hide_default_sidebar_pages()
    with st.sidebar:
        st.markdown("### ETOZ Student")
        st.page_link("pages/Dashboard.py", label="Dashboard", icon="📊")
        st.page_link("pages/Classes.py", label="Classes", icon="🏫")
        st.page_link("pages/Modules.py", label="Modules", icon="📘")
        st.page_link("pages/Profile.py", label="Profile", icon="👤")
        st.divider()
        if st.button("Log out", width="stretch", key="student_logout"):
            clear_auth_session()
            st.switch_page("app.py")


def render_teacher_sidebar(active: str | None = None) -> None:
    """Teacher-only navigation links."""

    del active
    hide_default_sidebar_pages()
    with st.sidebar:
        st.markdown("### ETOZ Teacher")
        st.page_link("pages/_TeacherHome.py", label="Home", icon="🏠")
        st.page_link("pages/_ClassManager.py", label="Classes", icon="🏫")
        st.caption("Account")
        st.page_link("pages/Profile.py", label="Profile", icon="👤")
        st.divider()
        if st.button("Log out", width="stretch", key="teacher_logout"):
            clear_auth_session()
            st.switch_page("app.py")


def render_public_sidebar() -> None:
    """Guest navigation — browse content without an account when public mode is on."""

    hide_default_sidebar_pages()
    with st.sidebar:
        st.markdown("### ETOZ")
        st.page_link("app.py", label="Home", icon="🏠")
        if is_public_mode():
            st.caption("Browse freely — or log in to save progress / teach")
            st.page_link("pages/Classes.py", label="Browse classes", icon="📚")
            st.page_link("pages/ClassHome.py", label="Class home", icon="🏫")
            st.page_link("pages/Modules.py", label="Modules", icon="📘")
            st.page_link("pages/Practice.py", label="Quizzes", icon="🧠")
            st.divider()
        st.page_link("pages/Login.py", label="Log in", icon="🔐")
        st.page_link("pages/Register.py", label="Register", icon="📝")


def render_nav_for_current_user() -> None:
    """Pick the correct sidebar after session init."""

    init_session_state()
    if is_logged_in():
        role = (st.session_state.current_user or {}).get("role")
        if role == "admin":
            render_teacher_sidebar()
        else:
            render_student_sidebar()
        return
    render_public_sidebar()
