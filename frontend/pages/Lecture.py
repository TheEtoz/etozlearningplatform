"""Student lecture — pages (subtopics) inside one selected module/topic."""

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

from frontend.utils.api import (
    APIError,
    check_mcq_answer,
    get_coding_path,
    get_demo_class,
    run_code,
    submit_code,
)
from frontend.utils.guards import require_student
from frontend.utils.lecture_pages import split_module_pages
from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import get_access_token, init_session_state, is_logged_in
from frontend.utils.ui import (
    media_from_payload,
    render_markdown_content,
    render_media_item,
    render_preserved_text,
    shuffled_mcq_choices,
)

st.set_page_config(page_title="Lecture | ETOZ", page_icon="📖", layout="wide")
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
    st.warning("Lectures live inside a class. Open a class first.")
    st.page_link("pages/Classes.py", label="Go to Classes", icon="🏫")
    st.stop()

ACTIVE_CLASS_ID = int(st.session_state.active_class_id)
ACTIVE_CLASS_TITLE = st.session_state.get("active_class_title") or "Class"

if "lecture_code" not in st.session_state:
    st.session_state.lecture_code = {}
if "lecture_result" not in st.session_state:
    st.session_state.lecture_result = {}

token = get_access_token()

try:
    modules = get_coding_path(token, ACTIVE_CLASS_ID)
except APIError as error:
    st.error(str(error))
    st.stop()

st.markdown(
    """
    <style>
    .lecture-read {
        max-width: 52rem;
        line-height: 1.7;
    }
    .lecture-read h1, .lecture-read h2, .lecture-read h3 {
        margin-top: 1.4rem;
        margin-bottom: 0.55rem;
        line-height: 1.25;
    }
    .lecture-read p { margin: 0.55rem 0 0.85rem 0; }
    .lecture-meta {
        color: #64748b;
        font-size: 0.9rem;
        margin: 0.15rem 0 1rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.page_link("pages/Modules.py", label="← Back to modules", icon="📘")

if not modules:
    st.info("No modules published in this class yet.")
    st.stop()

module_by_id = {int(module["id"]): module for module in modules}
module_id = st.session_state.get("active_module_id")
if module_id is None or int(module_id) not in module_by_id:
    st.info("Pick a module to start learning.")
    st.page_link("pages/Modules.py", label="Open modules", icon="📘")
    st.stop()

module = module_by_id[int(module_id)]
pages = split_module_pages(module.get("blocks") or [])
PAGE_KEY = f"lecture_page_idx_{module['id']}"
if PAGE_KEY not in st.session_state:
    st.session_state[PAGE_KEY] = 0
page_index = int(st.session_state[PAGE_KEY])
if page_index < 0 or page_index >= len(pages):
    page_index = 0
    st.session_state[PAGE_KEY] = 0

st.title(module["title"])
st.caption(f"{ACTIVE_CLASS_TITLE} · module")

page_labels = {
    f"{index + 1}. {page['title']}": index for index, page in enumerate(pages)
}
prev_col, pick_col, next_col = st.columns([1, 3.2, 1], gap="small")
with prev_col:
    if st.button(
        "← Prev",
        width="stretch",
        disabled=page_index == 0,
        key="lec_prev_page",
    ):
        st.session_state[PAGE_KEY] = page_index - 1
        st.rerun()
with pick_col:
    selected_label = st.selectbox(
        "Subsection",
        options=list(page_labels.keys()),
        index=page_index,
        label_visibility="collapsed",
    )
    selected_index = page_labels[selected_label]
    if selected_index != page_index:
        st.session_state[PAGE_KEY] = selected_index
        st.rerun()
with next_col:
    if st.button(
        "Next →",
        width="stretch",
        disabled=page_index >= len(pages) - 1,
        type="primary",
        key="lec_next_page",
    ):
        st.session_state[PAGE_KEY] = page_index + 1
        st.rerun()

page = pages[int(st.session_state[PAGE_KEY])]
page_index = int(st.session_state[PAGE_KEY])


def _render_mcq(block: dict) -> None:
    qid = block.get("question_id")
    choices = block.get("choices") or []
    if not choices:
        st.info("No choices available.")
        return
    block_id = block.get("id") or 0
    display_choices = shuffled_mcq_choices(
        choices,
        cache_key=f"lec_{ACTIVE_CLASS_ID}_{block_id}_{qid}",
        seed=int(ACTIVE_CLASS_ID) * 100_000
        + int(block_id) * 1_000
        + int(qid or 0),
    )
    answer = st.radio(
        "Choose one",
        display_choices,
        index=None,
        key=f"lec_mcq_{block.get('id')}_{qid}",
    )
    if st.button(
        "Check answer",
        type="primary",
        key=f"lec_mcq_check_{block.get('id')}",
    ):
        if not answer:
            st.warning("Pick an answer first.")
            return
        try:
            feedback = check_mcq_answer(token, int(qid), answer)
            if feedback.get("is_correct"):
                st.success("Correct!")
            else:
                st.error(
                    "Not quite. Correct answer: "
                    f"{feedback.get('correct_answer')}"
                )
        except APIError as error:
            st.error(str(error))


def _render_coding(block: dict) -> None:
    qid = int(block["question_id"])
    key = str(block.get("id") or qid)
    if key not in st.session_state.lecture_code:
        st.session_state.lecture_code[key] = block.get("starter_code") or ""

    st.session_state.lecture_code[key] = st.text_area(
        "Your Python code",
        value=st.session_state.lecture_code[key],
        height=240,
        key=f"lec_code_area_{key}",
    )
    run_col, submit_col = st.columns(2)
    with run_col:
        if st.button("Run", width="stretch", key=f"lec_run_{key}"):
            try:
                st.session_state.lecture_result[key] = {
                    "kind": "run",
                    "data": run_code(token, st.session_state.lecture_code[key]),
                }
            except APIError as error:
                st.error(str(error))
    with submit_col:
        if st.button(
            "Submit",
            type="primary",
            width="stretch",
            key=f"lec_submit_{key}",
        ):
            try:
                st.session_state.lecture_result[key] = {
                    "kind": "submit",
                    "data": submit_code(
                        token,
                        qid,
                        st.session_state.lecture_code[key],
                        class_id=ACTIVE_CLASS_ID,
                    ),
                }
            except APIError as error:
                st.error(str(error))

    result = st.session_state.lecture_result.get(key)
    if not result:
        return
    data = result["data"]
    if result["kind"] == "run":
        st.code(data.get("stdout") or "(no output)", language="text")
        if data.get("stderr"):
            st.error(data["stderr"])
        return
    status = data.get("status")
    if status == "passed":
        st.success(
            f"Passed · {data.get('tests_passed')}/{data.get('tests_total')}"
        )
    else:
        st.warning(
            f"{status} · score {data.get('score')} · "
            f"{data.get('tests_passed')}/{data.get('tests_total')}"
        )
    if data.get("stderr"):
        st.error(data["stderr"])


st.subheader(page["title"])
difficulty = module.get("difficulty_label") or "Topic"
st.markdown(
    f'<p class="lecture-meta">{difficulty} · '
    f"Subsection {page_index + 1} of {len(pages)}</p>",
    unsafe_allow_html=True,
)

blocks = page.get("blocks") or []
st.markdown('<div class="lecture-read">', unsafe_allow_html=True)
if not blocks and module.get("description") and page_index == 0:
    render_markdown_content(module.get("description") or "")

for block in blocks:
    btype = block.get("type") or "lecture"
    if btype == "page":
        continue
    if btype in ("lecture", "text"):
        markdown = str((block.get("payload") or {}).get("markdown") or "")
        render_markdown_content(markdown, empty_caption="No content yet.")
        st.write("")
        continue

    if btype == "media":
        payload = block.get("payload") or {}
        caption = str(payload.get("title") or "").strip()
        with st.container(border=True):
            st.markdown(f"**Media**{f' — {caption}' if caption else ''}")
            item = media_from_payload(payload)
            if item:
                render_media_item(item)
            else:
                st.caption("No media in this section yet.")
        st.write("")
        continue

    title = block.get("title") or (
        "Multiple choice" if btype == "mcq" else "Coding practice"
    )
    done_flag = bool(block.get("is_completed"))
    with st.container(border=True):
        st.markdown(
            f"**{'Completed' if done_flag else 'Try this'}** — {title}"
        )
        render_preserved_text(block.get("description") or "")
        if btype == "mcq":
            _render_mcq(block)
        else:
            _render_coding(block)
    st.write("")
st.markdown("</div>", unsafe_allow_html=True)
