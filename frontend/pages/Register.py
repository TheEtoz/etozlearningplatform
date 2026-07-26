"""Streamlit registration — redirects to the correct hub by role."""

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
    register_user,
)
from frontend.utils.guards import hub_for_role
from frontend.utils.nav import render_nav_for_current_user, render_public_sidebar
from frontend.utils.session import init_session_state, is_logged_in, save_auth_session

st.set_page_config(page_title="Register | ETOZ", page_icon="📝", layout="centered")
init_session_state()

if is_logged_in():
    render_nav_for_current_user()
    user = st.session_state.current_user or {}
    st.switch_page(hub_for_role(user.get("role")))

render_public_sidebar()

st.title("Create account")
st.caption("New accounts are students unless the username is listed in ADMIN_USERNAMES.")

if not check_backend_health():
    st.error("Backend is not reachable. Start it with: `python run_backend.py`")
    st.stop()

with st.form("register_form"):
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Register", type="primary")

if submitted:
    if not username or not email or not password:
        st.error("Please fill in all fields.")
    else:
        try:
            register_user(username, email, password)
            token_data = login_user(username, password)
            user = get_current_user(token_data["access_token"])
            save_auth_session(token_data["access_token"], user)
            st.switch_page(hub_for_role(user.get("role")))
        except APIError as error:
            st.error(str(error))

st.divider()
st.page_link("pages/Login.py", label="Already have an account?", icon="🔐")
st.page_link("app.py", label="Back to Home", icon="🏠")
