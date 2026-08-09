"""Set a new password from an emailed reset token."""

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

from frontend.utils.api import APIError, check_backend_health, reset_password
from frontend.utils.nav import render_public_sidebar
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Reset password | ETOZ", page_icon="🔑", layout="centered")
init_session_state()
render_public_sidebar()

st.title("Reset password")
st.caption("Use the link from your email, then choose a new password.")

if not check_backend_health():
    st.error("Backend is not reachable.")
    st.stop()

token = st.query_params.get("token") or ""
with st.form("reset_form"):
    token_input = st.text_input("Reset token", value=token)
    password = st.text_input("New password", type="password")
    password2 = st.text_input("Confirm new password", type="password")
    submitted = st.form_submit_button("Update password", type="primary")

if submitted:
    if not (token_input or "").strip():
        st.error("Missing reset token.")
    elif not password or len(password) < 8:
        st.error("Password must be at least 8 characters.")
    elif password != password2:
        st.error("Passwords do not match.")
    else:
        try:
            result = reset_password(token_input.strip(), password)
            st.success(result.get("message") or "Password updated.")
            st.page_link("pages/Login.py", label="Go to Login", icon="🔐")
        except APIError as error:
            st.error(str(error))

st.page_link("pages/Login.py", label="Back to Login", icon="🔐")
