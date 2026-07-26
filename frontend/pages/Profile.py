"""Account profile and logout."""

import importlib
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

import frontend.utils.api as _api

importlib.reload(_api)

from frontend.utils.api import APIError, get_current_user
from frontend.utils.guards import hub_for_role, require_login
from frontend.utils.session import (
    clear_auth_session,
    get_access_token,
    init_session_state,
    save_auth_session,
)

st.set_page_config(page_title="Profile | ETOZ", page_icon="👤", layout="centered")
init_session_state()
user = require_login()

token = get_access_token()
try:
    user = get_current_user(token)
    save_auth_session(token, user)
except APIError as error:
    st.error(str(error))
    clear_auth_session()
    st.page_link("pages/Login.py", label="Log in again", icon="🔐")
    st.stop()

st.title("Profile")
st.page_link(hub_for_role(user.get("role")), label="Back to Home", icon="🏠")
st.write(f"**Username:** {user['username']}")
st.write(f"**Email:** {user['email']}")
st.write(f"**Role:** {user.get('role', 'student')}")
st.write(f"**Joined:** {str(user.get('created_at', ''))[:10]}")

if st.button("Log out", type="primary"):
    clear_auth_session()
    st.switch_page("app.py")
