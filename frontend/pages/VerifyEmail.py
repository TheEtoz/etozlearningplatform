"""Confirm email from the link sent after registration."""

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

from frontend.utils.api import APIError, check_backend_health, verify_email
from frontend.utils.nav import render_public_sidebar
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Verify email | ETOZ", page_icon="✉️", layout="centered")
init_session_state()
render_public_sidebar()

st.title("Verify email")
st.caption("Open the link from your email, or paste the token below.")

if not check_backend_health():
    st.error("Backend is not reachable.")
    st.stop()

token = st.query_params.get("token") or ""
manual = st.text_input("Verification token", value=token)
if st.button("Verify email", type="primary"):
    if not (manual or "").strip():
        st.error("Missing token.")
    else:
        try:
            user = verify_email(manual.strip())
            st.session_state.pop("register_pending_email", None)
            st.success(
                f"Email verified for **{user.get('username')}**. You can log in now."
            )
        except APIError as error:
            st.error(str(error))

st.page_link("pages/Login.py", label="Go to Login", icon="🔐")
st.page_link("pages/Register.py", label="Back to Register", icon="📝")
