"""Request a password-reset email."""

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

from frontend.utils.api import APIError, check_backend_health, forgot_password
from frontend.utils.nav import render_public_sidebar
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Forgot password | ETOZ", page_icon="🔑", layout="centered")
init_session_state()
render_public_sidebar()

st.title("Forgot password")
st.caption("We'll email a reset link if that address has an account.")

if not check_backend_health():
    st.error("Backend is not reachable.")
    st.stop()

with st.form("forgot_form"):
    email = st.text_input("Email")
    submitted = st.form_submit_button("Send reset link", type="primary")

if submitted:
    if not email:
        st.error("Enter your email.")
    else:
        try:
            result = forgot_password(email.strip())
            st.success(result.get("message") or "If an account exists, we sent a link.")
        except APIError as error:
            st.error(str(error))

st.page_link("pages/Login.py", label="Back to Login", icon="🔐")
