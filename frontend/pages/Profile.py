"""Account profile and logout."""

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

from frontend.utils.api import APIError
from frontend.utils.guards import hub_for_role, require_login
from frontend.utils.session import (
    clear_auth_session,
    init_session_state,
    refresh_user_profile,
)

st.set_page_config(page_title="Profile | ETOZ", page_icon="👤", layout="centered")
init_session_state()
user = require_login()

try:
    refreshed = refresh_user_profile()
    if not refreshed:
        raise APIError("Session expired")
    user = refreshed
except APIError as error:
    st.error(str(error))
    clear_auth_session()
    st.page_link("pages/Login.py", label="Log in again", icon="🔐")
    st.stop()

st.title("Profile")
st.page_link(hub_for_role(user.get("role")), label="Back to Home", icon="🏠")
st.write(f"**Username:** {user['username']}")
st.write(f"**Email:** {user['email']}")
st.write(
    f"**Email verified:** "
    f"{'Yes' if user.get('email_verified') else 'No'}"
)
st.write(f"**Role:** {user.get('role', 'student')}")
st.write(f"**Joined:** {str(user.get('created_at', ''))[:10]}")

if st.button("Log out", type="primary"):
    clear_auth_session()
    st.switch_page("app.py")
