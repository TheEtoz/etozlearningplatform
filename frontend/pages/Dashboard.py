"""Student hub — enrolled classes plus learning stats."""

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
    get_progress,
    get_progress_summary,
    list_enrolled_classes,
    list_submissions,
)
from frontend.utils.guards import require_student
from frontend.utils.public_mode import is_public_mode
from frontend.utils.session import get_access_token, init_session_state, is_logged_in
from frontend.utils.ui import render_preserved_text

st.set_page_config(page_title="Dashboard | ETOZ", page_icon="📊", layout="wide")
init_session_state()
user = require_student()

# Guests have no dashboard — send them to public class content.
if is_public_mode() and not is_logged_in():
    st.switch_page("pages/ClassHome.py")

token = get_access_token()

st.title(f"Welcome, {user.get('username', 'student')}")
st.caption("Your student home — classes, progress, and recent activity.")

st.subheader("Your classes")
try:
    enrolled = list_enrolled_classes(token)
except APIError as error:
    st.error(str(error))
    enrolled = []

if not enrolled:
    st.info("Enroll in a class to access quizzes and lectures.")
    st.page_link("pages/Classes.py", label="Find a class", icon="🏫")
else:
    cols = st.columns(min(3, len(enrolled)))
    for index, classroom in enumerate(enrolled):
        with cols[index % len(cols)]:
            with st.container(border=True):
                st.markdown(f"**{classroom['title']}**")
                render_preserved_text(classroom.get("description") or "")
                st.caption(
                    f"{classroom.get('quiz_count', 0)} quizzes · "
                    f"{classroom.get('module_count', 0)} modules"
                )
                if st.button(
                    "Open",
                    key=f"dash_open_{classroom['id']}",
                    width="stretch",
                ):
                    st.session_state.active_class_id = classroom["id"]
                    st.session_state.active_class_title = classroom["title"]
                    st.switch_page("pages/ClassHome.py")
    st.page_link("pages/Classes.py", label="Browse or join more classes", icon="🏫")

st.divider()
st.subheader("Your progress")

try:
    summary = get_progress_summary(token)
    topics = get_progress(token)
    submissions = list_submissions(token)
except APIError as error:
    st.error(str(error))
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Questions attempted", summary.get("questions_attempted", 0))
col2.metric("Questions correct", summary.get("questions_correct", 0))
col3.metric("Overall accuracy", f"{summary.get('overall_accuracy', '0.00')}%")

weak = summary.get("weak_topics") or []
if weak:
    st.warning("Focus next: " + ", ".join(f"**{t}**" for t in weak))
else:
    st.success("No weak topics yet — keep practicing!")

if topics:
    rows = [
        {
            "topic": row["topic"],
            "accuracy": float(row["accuracy"]),
            "attempted": row["questions_attempted"],
            "correct": row["questions_correct"],
        }
        for row in topics
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.bar_chart({row["topic"]: row["accuracy"] for row in rows})
else:
    st.info("Complete a class quiz or coding level to see topic stats here.")

st.subheader("Recent activity")
if not submissions:
    st.caption("No submissions yet.")
else:
    for item in submissions[:10]:
        kind = "code" if item.get("code") else "MCQ"
        created = str(item.get("created_at", ""))[:19].replace("T", " ")
        st.markdown(
            f"- **Q#{item.get('question_id')}** ({kind}) — "
            f"`{item.get('status')}` · score **{item.get('score')}** · {created}"
        )
