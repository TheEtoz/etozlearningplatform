"""Module editor — Module (topic) → Subsections → lecture flow per subsection."""

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

import uuid

import streamlit as st

from frontend.utils.api import (
    APIError,
    create_question,
    delete_module,
    get_admin_module,
    list_admin_questions,
    list_media_library,
    list_subjects,
    set_module_blocks,
    update_module,
    upload_media,
)
from frontend.utils.guards import require_teacher
from frontend.utils.lecture_pages import blocks_to_subsections, subsections_to_blocks
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.ui import (
    bank_picker_filters,
    classify_media_url,
    mcq_choices_editor,
    media_from_payload,
    question_summary_label,
    render_markdown_content,
    render_media_item,
    render_question_preview,
    subject_area_picker,
    success_banner,
    test_case_editor,
    unsaved_changes_banner,
)

st.set_page_config(page_title="Module Editor | ETOZ", page_icon="📖", layout="wide")
init_session_state()
require_teacher()
token = get_access_token()

module_id = st.session_state.get("editor_module_id")
if not module_id:
    st.warning("Open a module from Class Manager.")
    st.page_link("pages/_ClassManager.py", label="Back to Classes", icon="🏫")
    st.stop()

try:
    module = get_admin_module(token, int(module_id))
    bank = list_admin_questions(token)
    subjects_tree = list_subjects(token)
except APIError as error:
    st.error(str(error))
    st.page_link("pages/_ClassManager.py", label="Back to Classes", icon="🏫")
    st.stop()

id_to_question = {q["id"]: q for q in bank}

st.page_link("pages/_ClassManager.py", label="← Back to Classes", icon="🏫")
st.title(module["title"])
st.caption(
    "Module (topic) → subsections (e.g. Matrix addition) → lecture flow inside each."
)

sub_key = f"mod_subsections_{module_id}"
snap_key = f"mod_blocks_snap_{module_id}"
active_sub_key = f"mod_active_sub_{module_id}"

server_blocks = [
    {
        "type": block["type"],
        "payload": dict(block.get("payload") or {}),
        "question_id": block.get("question_id"),
        "id": block.get("id"),
    }
    for block in (module.get("blocks") or [])
]
server_snap = list(server_blocks)

if sub_key not in st.session_state or st.session_state.get(snap_key) != server_snap:
    # Prefer one empty subsection for brand-new modules.
    if not server_blocks:
        st.session_state[sub_key] = [
            {
                "_uid": uuid.uuid4().hex[:12],
                "title": "Untitled subsection",
                "blocks": [
                    {
                        "type": "lecture",
                        "payload": {"markdown": ""},
                        "question_id": None,
                        "_uid": uuid.uuid4().hex[:12],
                    }
                ],
            }
        ]
    else:
        st.session_state[sub_key] = blocks_to_subsections(server_blocks)
    st.session_state[snap_key] = [dict(item) for item in server_snap]
    st.session_state[active_sub_key] = 0

subsections = list(st.session_state[sub_key])
if not subsections:
    subsections = [
        {
            "_uid": uuid.uuid4().hex[:12],
            "title": "Untitled subsection",
            "blocks": [],
        }
    ]
    st.session_state[sub_key] = subsections

active_index = int(st.session_state.get(active_sub_key) or 0)
if active_index < 0 or active_index >= len(subsections):
    active_index = 0
    st.session_state[active_sub_key] = 0


def _block_uid(block: dict) -> str:
    return str(block.get("_uid") or block.get("id") or id(block))


def _persist_subsections(rows: list[dict]) -> None:
    st.session_state[sub_key] = rows


def _current_flat_for_dirty() -> list[dict]:
    return [
        {
            "type": item["type"],
            "payload": {
                key: value
                for key, value in dict(item.get("payload") or {}).items()
                if not str(key).startswith("_")
            },
            "question_id": item.get("question_id"),
            "id": item.get("id"),
        }
        for item in subsections_to_blocks(subsections)
    ]


dirty = _current_flat_for_dirty() != list(st.session_state.get(snap_key, server_snap))
unsaved_changes_banner(
    dirty,
    message="Draft changed — press Save module to keep subsections and lecture flow.",
)

settings_tab, content_tab = st.tabs(["Settings", "Subsections"])


with settings_tab:
    etitle = st.text_input("Module title", value=module["title"], key=f"me_title_{module_id}")
    elabel = st.text_input(
        "Label",
        value=module.get("difficulty_label") or "",
        key=f"me_label_{module_id}",
    )
    if st.button("Save settings", type="primary", key=f"me_save_meta_{module_id}"):
        try:
            update_module(
                token,
                int(module_id),
                {
                    "title": etitle,
                    "difficulty_label": elabel or None,
                },
            )
            success_banner("Module settings saved.")
            st.rerun()
        except APIError as error:
            st.error(str(error))
    if st.button("Delete module", key=f"me_del_{module_id}"):
        try:
            delete_module(token, int(module_id))
            st.session_state.pop("editor_module_id", None)
            success_banner("Module deleted.")
            st.switch_page("pages/_ClassManager.py")
        except APIError as error:
            st.error(str(error))


def _sync_flow_widgets(flow: list[dict], *, section_uid: str) -> None:
    for block in flow:
        uid = _block_uid(block)
        btype = block.get("type") or "lecture"
        if btype in ("lecture", "text"):
            key = f"me_md_{module_id}_{section_uid}_{uid}"
            if key in st.session_state:
                block["payload"] = {"markdown": st.session_state[key]}
        elif btype == "media":
            payload = dict(block.get("payload") or {})
            title_key = f"me_media_title_{module_id}_{section_uid}_{uid}"
            if title_key in st.session_state:
                payload["title"] = st.session_state[title_key]
            if not str(payload.get("url") or "").strip():
                url_key = f"me_media_url_{module_id}_{section_uid}_{uid}"
                label_key = f"me_media_label_{module_id}_{section_uid}_{uid}"
                if url_key in st.session_state and st.session_state[url_key]:
                    url = str(st.session_state[url_key]).strip()
                    if url:
                        payload["url"] = url
                        payload["kind"] = classify_media_url(url)
                if label_key in st.session_state:
                    label = str(st.session_state[label_key] or "").strip()
                    payload["label"] = label or None
            legacy = media_from_payload(payload)
            if legacy and not str(payload.get("url") or "").strip():
                payload["url"] = legacy["url"]
                payload["kind"] = legacy["kind"]
                payload["label"] = legacy.get("label")
            payload.pop("items", None)
            payload.pop("markdown", None)
            block["payload"] = payload


def _move_flow_block(section_uid: str, uid: str, direction: int) -> None:
    rows = list(st.session_state[sub_key])
    section = next((row for row in rows if row["_uid"] == section_uid), None)
    if section is None:
        return
    flow = list(section.get("blocks") or [])
    _sync_flow_widgets(flow, section_uid=section_uid)
    index = next((i for i, block in enumerate(flow) if _block_uid(block) == uid), None)
    if index is None:
        return
    target = index + direction
    if target < 0 or target >= len(flow):
        return
    flow[index], flow[target] = flow[target], flow[index]
    section["blocks"] = flow
    _persist_subsections(rows)
    st.rerun()


def _insert_flow_block(section_uid: str, index: int, block: dict) -> None:
    rows = list(st.session_state[sub_key])
    section = next((row for row in rows if row["_uid"] == section_uid), None)
    if section is None:
        return
    flow = list(section.get("blocks") or [])
    _sync_flow_widgets(flow, section_uid=section_uid)
    block = dict(block)
    block.setdefault("_uid", uuid.uuid4().hex[:12])
    flow.insert(index, block)
    section["blocks"] = flow
    _persist_subsections(rows)
    st.rerun()


with content_tab:
    left, right = st.columns([1.15, 2.85], gap="large")

    with left:
        st.markdown("#### Subsections")
        st.caption("e.g. Matrix addition, Matrix multiplication")
        for index, section in enumerate(subsections):
            selected = index == active_index
            row = st.columns([6, 1, 1, 1])
            label = section.get("title") or "Untitled subsection"
            if row[0].button(
                f"{'● ' if selected else ''}{label}",
                key=f"me_sub_pick_{module_id}_{section['_uid']}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                # Sync title field before switching.
                title_key = f"me_sub_title_{module_id}_{subsections[active_index]['_uid']}"
                if title_key in st.session_state:
                    subsections[active_index]["title"] = (
                        str(st.session_state[title_key] or "").strip()
                        or "Untitled subsection"
                    )
                    _persist_subsections(subsections)
                st.session_state[active_sub_key] = index
                st.rerun()
            if row[1].button(
                "↑",
                key=f"me_sub_up_{module_id}_{section['_uid']}",
                disabled=index == 0,
            ):
                subsections[index - 1], subsections[index] = (
                    subsections[index],
                    subsections[index - 1],
                )
                st.session_state[active_sub_key] = index - 1
                _persist_subsections(subsections)
                st.rerun()
            if row[2].button(
                "↓",
                key=f"me_sub_dn_{module_id}_{section['_uid']}",
                disabled=index >= len(subsections) - 1,
            ):
                subsections[index + 1], subsections[index] = (
                    subsections[index],
                    subsections[index + 1],
                )
                st.session_state[active_sub_key] = index + 1
                _persist_subsections(subsections)
                st.rerun()
            if row[3].button(
                "✕",
                key=f"me_sub_rm_{module_id}_{section['_uid']}",
                disabled=len(subsections) <= 1,
            ):
                subsections.pop(index)
                st.session_state[active_sub_key] = min(index, len(subsections) - 1)
                _persist_subsections(subsections)
                st.rerun()

        new_title = st.text_input(
            "New subsection title",
            key=f"me_sub_new_title_{module_id}",
            placeholder="Matrix addition",
        )
        if st.button("Add subsection", type="primary", key=f"me_sub_add_{module_id}"):
            title = (new_title or "").strip() or "Untitled subsection"
            subsections.append(
                {
                    "_uid": uuid.uuid4().hex[:12],
                    "title": title,
                    "blocks": [],
                }
            )
            st.session_state[active_sub_key] = len(subsections) - 1
            _persist_subsections(subsections)
            st.rerun()

    section = subsections[active_index]
    section_uid = section["_uid"]
    flow = list(section.get("blocks") or [])

    with right:
        st.markdown("#### Lecture flow")
        title_key = f"me_sub_title_{module_id}_{section_uid}"
        if title_key not in st.session_state:
            st.session_state[title_key] = section.get("title") or ""
        section["title"] = st.text_input(
            "Subsection title",
            key=title_key,
        ).strip() or "Untitled subsection"
        st.caption("Blocks below belong only to this subsection.")

        type_labels = {
            "lecture": "📖 Lecture",
            "text": "📝 Note",
            "media": "🎬 Multimedia",
            "mcq": "🧠 MCQ",
            "coding": "💻 Coding",
        }

        def _set_single_media(
            block: dict, *, url: str, kind: str, label: str | None
        ) -> None:
            payload = dict(block.get("payload") or {})
            media_title_key = f"me_media_title_{module_id}_{section_uid}_{_block_uid(block)}"
            if media_title_key in st.session_state:
                payload["title"] = st.session_state[media_title_key]
            payload["url"] = url
            payload["kind"] = kind
            payload["label"] = label
            payload.pop("items", None)
            payload.pop("markdown", None)
            block["payload"] = payload
            rows = list(st.session_state[sub_key])
            for row in rows:
                if row["_uid"] != section_uid:
                    continue
                updated = []
                for existing in row.get("blocks") or []:
                    if _block_uid(existing) == _block_uid(block):
                        updated.append(block)
                    else:
                        updated.append(existing)
                row["blocks"] = updated
            _persist_subsections(rows)
            st.rerun()

        def _render_insert_panel(after_index: int) -> None:
            insert_at = after_index + 1
            open_key = f"me_ins_open_{module_id}_{section_uid}_{after_index}"
            label = "＋ Insert below" if after_index >= 0 else "＋ Insert at start"
            if st.button(label, key=f"me_ins_toggle_{module_id}_{section_uid}_{after_index}"):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()
            if not st.session_state.get(open_key):
                return

            with st.container(border=True):
                kind = st.selectbox(
                    "Block type",
                    ["lecture", "media", "mcq", "coding", "text"],
                    key=f"me_ins_kind_{module_id}_{section_uid}_{after_index}",
                    format_func=lambda value: {
                        "lecture": "Lecture section",
                        "media": "Multimedia (video / image / file)",
                        "text": "Short note",
                        "mcq": "MCQ practice",
                        "coding": "Coding practice",
                    }[value],
                )
                if kind in ("lecture", "text", "media"):
                    if st.button(
                        f"Insert {kind} block",
                        key=f"me_ins_text_{module_id}_{section_uid}_{after_index}",
                        type="primary",
                    ):
                        st.session_state[open_key] = False
                        _insert_flow_block(
                            section_uid,
                            insert_at,
                            {
                                "type": kind,
                                "payload": (
                                    {"title": "", "url": "", "kind": "", "label": None}
                                    if kind == "media"
                                    else {"markdown": ""}
                                ),
                                "question_id": None,
                            },
                        )
                    return

                create_tab, import_tab = st.tabs(["Create new", "Import from bank"])
                with create_tab:
                    prefix = (
                        f"me_ins_create_{module_id}_{section_uid}_{after_index}_{kind}"
                    )
                    title = st.text_input("Title", key=f"{prefix}_title")
                    description = st.text_area(
                        "Prompt (optional)", height=90, key=f"{prefix}_desc"
                    )
                    difficulty = st.selectbox(
                        "Difficulty",
                        ["easy", "medium", "hard"],
                        key=f"{prefix}_diff",
                    )
                    visibility = st.selectbox(
                        "Sharing",
                        ["private", "public"],
                        format_func=lambda value: (
                            "Private — only you"
                            if value == "private"
                            else "Shared — Global Question Bank"
                        ),
                        key=f"{prefix}_vis",
                    )
                    subject, areas = subject_area_picker(
                        subjects_tree=subjects_tree,
                        key_prefix=prefix,
                    )
                    if kind == "mcq":
                        choices, correct_answer = mcq_choices_editor(f"{prefix}_mcq")
                        cases: list[dict] = []
                        starter_code = ""
                    else:
                        starter_code = st.text_area(
                            "Starter code",
                            value='print("Hello")\n',
                            height=110,
                            key=f"{prefix}_starter",
                        )
                        cases = test_case_editor(f"{prefix}_cases")
                        choices, correct_answer = [], None
                    if st.button(
                        "Create & insert",
                        type="primary",
                        key=f"{prefix}_submit",
                    ):
                        if len((title or "").strip()) < 3:
                            st.error("Title needs at least 3 characters.")
                        elif not areas:
                            st.error("Pick at least one area.")
                        else:
                            payload = {
                                "title": title.strip(),
                                "description": description or "",
                                "type": kind,
                                "difficulty": difficulty,
                                "subject": subject,
                                "topics": areas,
                                "visibility": visibility,
                                "language": "python",
                            }
                            try:
                                if kind == "mcq":
                                    if len(choices) < 2 or not correct_answer:
                                        st.error(
                                            "Add at least two options and pick the answer."
                                        )
                                        st.stop()
                                    payload["choices"] = choices
                                    payload["correct_answer"] = correct_answer
                                else:
                                    if not cases:
                                        st.error("Add at least one test case.")
                                        st.stop()
                                    payload["starter_code"] = starter_code
                                    payload["test_cases"] = cases
                                question = create_question(token, payload)
                                st.session_state[open_key] = False
                                _insert_flow_block(
                                    section_uid,
                                    insert_at,
                                    {
                                        "type": kind,
                                        "payload": {},
                                        "question_id": question["id"],
                                    },
                                )
                            except APIError as error:
                                st.error(str(error))

                with import_tab:
                    used_ids = {
                        block.get("question_id")
                        for block in flow
                        if block.get("type") == kind and block.get("question_id")
                    }
                    candidates = [
                        question
                        for question in bank
                        if question.get("type") == kind
                        and question["id"] not in used_ids
                    ]
                    filtered = bank_picker_filters(
                        candidates,
                        key_prefix=(
                            f"me_ins_pick_{module_id}_{section_uid}_{after_index}_{kind}"
                        ),
                        allow_type_filter=False,
                    )
                    for question in filtered[:15]:
                        with st.container(border=True):
                            st.markdown(f"**{question_summary_label(question)}**")
                            render_question_preview(question, show_answers=True)
                            if st.button(
                                "Insert this question",
                                key=(
                                    f"me_ins_q_{module_id}_{section_uid}_"
                                    f"{after_index}_{question['id']}"
                                ),
                            ):
                                st.session_state[open_key] = False
                                _insert_flow_block(
                                    section_uid,
                                    insert_at,
                                    {
                                        "type": kind,
                                        "payload": {},
                                        "question_id": question["id"],
                                    },
                                )

        _render_insert_panel(-1)
        if not flow:
            st.info("Add lecture / media / practice blocks for this subsection.")

        for index, block in enumerate(flow):
            uid = _block_uid(block)
            btype = block.get("type") or "lecture"
            qid = block.get("question_id")
            question = id_to_question.get(qid) if qid else None
            if btype in ("lecture", "text", "media"):
                header = f"{index + 1}. {type_labels.get(btype, btype)}"
                media_title = str((block.get("payload") or {}).get("title") or "").strip()
                if btype == "media" and media_title:
                    header = f"{header} · {media_title}"
            elif question:
                header = (
                    f"{index + 1}. {type_labels.get(btype, btype)} · {question['title']}"
                )
            else:
                header = f"{index + 1}. {type_labels.get(btype, btype)} · #{qid or '—'}"

            with st.container(border=True):
                top = st.columns([8, 1, 1, 1])
                with top[0]:
                    st.markdown(f"**{header}**")
                if top[1].button(
                    "↑",
                    key=f"me_up_{module_id}_{section_uid}_{uid}",
                    disabled=index == 0,
                ):
                    _move_flow_block(section_uid, uid, -1)
                if top[2].button(
                    "↓",
                    key=f"me_dn_{module_id}_{section_uid}_{uid}",
                    disabled=index >= len(flow) - 1,
                ):
                    _move_flow_block(section_uid, uid, 1)
                if top[3].button("✕", key=f"me_rm_{module_id}_{section_uid}_{uid}"):
                    rows = list(st.session_state[sub_key])
                    for row in rows:
                        if row["_uid"] != section_uid:
                            continue
                        _sync_flow_widgets(flow, section_uid=section_uid)
                        row["blocks"] = [
                            item for item in flow if _block_uid(item) != uid
                        ]
                    _persist_subsections(rows)
                    st.rerun()

                if btype == "media":
                    st.caption(
                        "One media item: caption, then URL, upload, or library. "
                        "Files download for students."
                    )
                    media_title_key = f"me_media_title_{module_id}_{section_uid}_{uid}"
                    if media_title_key not in st.session_state:
                        st.session_state[media_title_key] = str(
                            (block.get("payload") or {}).get("title") or ""
                        )
                    title = st.text_input("Caption (optional)", key=media_title_key)
                    current = media_from_payload(block.get("payload") or {})
                    if current:
                        with st.expander("Student preview", expanded=True):
                            render_media_item(current)
                        if st.button(
                            "Clear media",
                            key=f"me_media_clear_{module_id}_{section_uid}_{uid}",
                        ):
                            block["payload"] = {
                                "title": title,
                                "url": "",
                                "kind": "",
                                "label": None,
                            }
                            st.session_state[
                                f"me_media_url_{module_id}_{section_uid}_{uid}"
                            ] = ""
                            st.session_state[
                                f"me_media_label_{module_id}_{section_uid}_{uid}"
                            ] = ""
                            rows = list(st.session_state[sub_key])
                            for row in rows:
                                if row["_uid"] == section_uid:
                                    row["blocks"] = [
                                        block if _block_uid(item) == uid else item
                                        for item in (row.get("blocks") or [])
                                    ]
                            _persist_subsections(rows)
                            st.rerun()
                    else:
                        url_key = f"me_media_url_{module_id}_{section_uid}_{uid}"
                        label_key = f"me_media_label_{module_id}_{section_uid}_{uid}"
                        if url_key not in st.session_state:
                            st.session_state[url_key] = ""
                        if label_key not in st.session_state:
                            st.session_state[label_key] = ""
                        link_url = st.text_input(
                            "Link (YouTube, image, video, or file URL)",
                            key=url_key,
                        )
                        link_label = st.text_input(
                            "Link label (optional, for downloads)",
                            key=label_key,
                        )
                        if st.button(
                            "Use this link",
                            key=f"me_media_url_btn_{module_id}_{section_uid}_{uid}",
                            type="primary",
                        ):
                            url = (link_url or "").strip()
                            if not url:
                                st.error("Enter a URL.")
                            else:
                                _set_single_media(
                                    block,
                                    url=url,
                                    kind=classify_media_url(url),
                                    label=(link_label or "").strip() or None,
                                )
                        st.markdown("**or upload a file**")
                        up = st.file_uploader(
                            "Upload image, video, or file",
                            key=f"me_media_upl_{module_id}_{section_uid}_{uid}",
                            type=[
                                "png",
                                "jpg",
                                "jpeg",
                                "gif",
                                "webp",
                                "mp4",
                                "webm",
                                "pdf",
                                "zip",
                                "txt",
                                "csv",
                                "py",
                            ],
                        )
                        if up is not None and st.button(
                            "Use this upload",
                            key=f"me_media_upl_btn_{module_id}_{section_uid}_{uid}",
                        ):
                            try:
                                result = upload_media(
                                    token, up.name, up.getvalue(), up.type
                                )
                                kind = result.get("kind") or "download"
                                if kind == "file":
                                    kind = "download"
                                _set_single_media(
                                    block,
                                    url=result["url"],
                                    kind=kind,
                                    label=result.get("filename") or "Download file",
                                )
                            except APIError as error:
                                st.error(str(error))
                        with st.expander("Pick from library", expanded=False):
                            try:
                                library = list_media_library(token)
                            except APIError as error:
                                st.error(str(error))
                                library = []
                            if not library:
                                st.caption("No uploads yet.")
                            for item in library[:40]:
                                kind = item.get("kind") or "file"
                                label = item.get("filename") or item.get("stored_name")
                                pick = st.columns([4, 1])
                                pick[0].caption(f"{kind} · {label}")
                                if pick[1].button(
                                    "Use",
                                    key=(
                                        f"me_lib_{module_id}_{section_uid}_{uid}_"
                                        f"{item['stored_name']}"
                                    ),
                                ):
                                    use_kind = "download" if kind == "file" else kind
                                    use_url = (
                                        item.get("download_url")
                                        if use_kind == "download"
                                        else item.get("url")
                                    )
                                    _set_single_media(
                                        block,
                                        url=str(use_url or item.get("url")),
                                        kind=use_kind,
                                        label=str(label),
                                    )
                    payload = dict(block.get("payload") or {})
                    payload["title"] = title
                    payload.pop("items", None)
                    payload.pop("markdown", None)
                    block["payload"] = payload

                elif btype in ("lecture", "text"):
                    st.caption(
                        "Write LaTeX or Markdown (colours, keypoints/note boxes, "
                        "TikZ, math). Students only see the compiled view."
                    )
                    widget_key = f"me_md_{module_id}_{section_uid}_{uid}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = str(
                            (block.get("payload") or {}).get("markdown") or ""
                        )
                    markdown = st.text_area(
                        "Source (teachers only)",
                        height=220,
                        key=widget_key,
                    )
                    block["payload"] = {"markdown": markdown}
                    st.markdown("**Student preview**")
                    render_markdown_content(
                        markdown,
                        empty_caption="No lecture content yet.",
                    )
                elif question:
                    render_question_preview(question, show_answers=True)
                else:
                    st.warning("Linked question missing from bank.")

            _render_insert_panel(index)

        # Keep subsection title + flow in session.
        section["blocks"] = flow
        subsections[active_index] = section
        _persist_subsections(subsections)

        if st.button(
            "Save module",
            type="primary",
            key=f"me_save_blocks_{module_id}",
        ):
            try:
                rows = list(st.session_state[sub_key])
                for row in rows:
                    _sync_flow_widgets(
                        list(row.get("blocks") or []),
                        section_uid=row["_uid"],
                    )
                    title_widget = f"me_sub_title_{module_id}_{row['_uid']}"
                    if title_widget in st.session_state:
                        row["title"] = (
                            str(st.session_state[title_widget] or "").strip()
                            or "Untitled subsection"
                        )
                flat = subsections_to_blocks(rows)
                payload = [
                    {
                        "type": item["type"],
                        "payload": {
                            key: value
                            for key, value in dict(item.get("payload") or {}).items()
                            if not str(key).startswith("_")
                        },
                        "question_id": item.get("question_id"),
                    }
                    for item in flat
                ]
                saved = set_module_blocks(token, int(module_id), payload)
                refreshed_blocks = [
                    {
                        "type": item["type"],
                        "payload": dict(item.get("payload") or {}),
                        "question_id": item.get("question_id"),
                        "id": item.get("id"),
                    }
                    for item in (saved.get("blocks") or payload)
                ]
                st.session_state[sub_key] = blocks_to_subsections(refreshed_blocks)
                st.session_state[snap_key] = refreshed_blocks
                success_banner("Module saved.")
                st.rerun()
            except APIError as error:
                st.error(str(error))
