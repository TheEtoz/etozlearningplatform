"""Compatibility redirect — old links pointed here after login."""

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

from frontend.utils.guards import require_student
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Student Home | ETOZ", page_icon="🏠", layout="centered")
init_session_state()
require_student()
st.switch_page("pages/Dashboard.py")
