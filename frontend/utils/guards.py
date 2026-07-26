"""Role and auth guards shared by Streamlit pages."""

from __future__ import annotations

import streamlit as st

from frontend.utils.nav import render_nav_for_current_user
from frontend.utils.session import init_session_state, is_logged_in, refresh_user_profile


def require_login() -> dict:
    """Stop the page unless the visitor is authenticated."""

    init_session_state()
    render_nav_for_current_user()
    if not is_logged_in():
        st.warning("Please log in to continue.")
        st.page_link("pages/Login.py", label="Go to Login", icon="🔐")
        st.stop()

    user = st.session_state.current_user or {}
    if not user.get("id"):
        user = refresh_user_profile() or {}
        if not user:
            st.warning("Your session expired. Please log in again.")
            st.page_link("pages/Login.py", label="Go to Login", icon="🔐")
            st.stop()
    return user


def require_student() -> dict:
    """Allow only student accounts on student pages."""

    user = require_login()
    if user.get("role") == "admin":
        st.warning("This page is for students only.")
        st.page_link("pages/_TeacherHome.py", label="Go to Teacher Home", icon="🛠️")
        st.stop()
    return user


def require_teacher() -> dict:
    """Allow only admin/teacher accounts on teacher pages."""

    user = require_login()
    if user.get("role") != "admin":
        st.error("This page is for teachers only.")
        st.page_link("pages/Dashboard.py", label="Go to Dashboard", icon="📊")
        st.stop()
    return user


def hub_for_role(role: str | None) -> str:
    """Return the Streamlit page path for a role after login."""

    if role == "admin":
        return "pages/_TeacherHome.py"
    return "pages/Dashboard.py"
