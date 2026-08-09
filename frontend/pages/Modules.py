"""Module hub — even cards: number, title, Learn only."""

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

import html

import streamlit as st

import importlib
import frontend.utils.reload as _etoz_reload

importlib.reload(_etoz_reload)
_etoz_reload.reload_frontend_utils()

from frontend.utils.api import APIError, get_coding_path, get_demo_class
from frontend.utils.guards import require_student
from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import get_access_token, init_session_state, is_logged_in

st.set_page_config(page_title="Modules | ETOZ", page_icon="📘", layout="wide")
init_session_state()
require_student()

if (
    not st.session_state.get("active_class_id")
    and is_public_mode()
    and not is_logged_in()
):
    try:
        demo = get_demo_class()
        st.session_state.active_class_id = demo["id"]
        st.session_state.active_class_title = demo["title"]
    except APIError:
        pass

if not st.session_state.get("active_class_id"):
    st.warning("Open a class first.")
    st.page_link("pages/Classes.py", label="Go to Classes", icon="🏫")
    st.stop()

ACTIVE_CLASS_ID = int(st.session_state.active_class_id)
ACTIVE_CLASS_TITLE = st.session_state.get("active_class_title") or "Class"
token = get_access_token()

try:
    modules = get_coding_path(token, ACTIVE_CLASS_ID)
except APIError as error:
    st.error(str(error))
    st.stop()

st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100%;
    }
    .mod-card-inner {
        min-height: 220px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        padding: 0.35rem 0.25rem 0.15rem;
    }
    .mod-circle {
        width: 4.5rem;
        height: 4.5rem;
        border-radius: 999px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        color: #0f172a;
        background: linear-gradient(145deg, #e8f0ec 0%, #d5e5db 100%);
        border: 2px solid rgba(15, 23, 42, 0.12);
        margin: 0.25rem auto 1rem auto;
        flex-shrink: 0;
    }
    .mod-title {
        text-align: center;
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
        line-height: 1.3;
        height: 2.6rem;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.page_link("pages/ClassHome.py", label="← Back to class", icon="🏫")
st.title(ACTIVE_CLASS_TITLE)
st.caption("Modules")

if not modules:
    st.info("No modules published in this class yet.")
    st.stop()

cols = st.columns(3, gap="large")
for index, module in enumerate(modules):
    with cols[index % 3]:
        with st.container(border=True):
            number = f"{index + 1:02d}"
            title = html.escape(str(module.get("title") or "Module"))
            st.markdown(
                f'<div class="mod-card-inner">'
                f'<div class="mod-circle">{number}</div>'
                f'<p class="mod-title">{title}</p>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "Learn",
                key=f"learn_mod_{module['id']}",
                type="primary",
                width="stretch",
            ):
                st.session_state.active_module_id = int(module["id"])
                st.session_state.active_module_title = module["title"]
                st.session_state[f"lecture_page_idx_{module['id']}"] = 0
                st.switch_page("pages/Lecture.py")
