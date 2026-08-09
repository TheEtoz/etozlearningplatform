"""Streamlit login page — redirects to the correct hub by role."""

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

from frontend.utils.api import (
    APIError,
    check_backend_health,
    get_current_user,
    login_user,
)
from frontend.utils.guards import hub_for_role
from frontend.utils.nav import render_nav_for_current_user, render_public_sidebar
from frontend.utils.session import init_session_state, is_logged_in, save_auth_session

st.set_page_config(page_title="Login | ETOZ", page_icon="🔐", layout="centered")
init_session_state()

if is_logged_in():
    render_nav_for_current_user()
    user = st.session_state.current_user or {}
    st.switch_page(hub_for_role(user.get("role")))

render_public_sidebar()

st.title("Log in")
st.caption("Students and teachers use the same login. Your hub opens after sign-in.")

if not check_backend_health():
    st.error("Backend is not reachable. Start it with: `python run_backend.py`")
    st.stop()

with st.form("login_form", clear_on_submit=False):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Login", type="primary")

if submitted:
    if not username or not password:
        st.error("Please enter both username and password.")
    else:
        try:
            token_data = login_user(username, password)
            access_token = token_data["access_token"]
            user = get_current_user(access_token)
            save_auth_session(access_token, user)
            st.rerun()
        except APIError as error:
            st.error(str(error))

st.divider()
st.page_link("pages/ForgotPassword.py", label="Forgot password?", icon="🔑")
st.page_link("pages/Register.py", label="Create an account", icon="📝")
st.page_link("app.py", label="Back to Home", icon="🏠")
