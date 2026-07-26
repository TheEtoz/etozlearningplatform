"""Student hub — practice entry points plus learning stats."""

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

from frontend.utils.api import (
    APIError,
    get_progress,
    get_progress_summary,
    list_submissions,
)
from frontend.utils.guards import require_student
from frontend.utils.session import init_session_state

st.set_page_config(page_title="Dashboard | ETOZ", page_icon="📊", layout="wide")
init_session_state()
user = require_student()

st.title(f"Welcome, {user.get('username', 'student')}")
st.caption("Your student home — practice, progress, and recent activity.")

c1, c2 = st.columns(2, gap="large")
with c1:
    with st.container(border=True):
        st.subheader("Practice Quizzes")
        st.write(
            "Timed and untimed quizzes from the bank. MCQ and coding can be mixed."
        )
        st.page_link("pages/Practice.py", label="Open quizzes", icon="🧠")
with c2:
    with st.container(border=True):
        st.subheader("Coding Path")
        st.write(
            "Module-by-module trail of coding levels. Jump freely to any node."
        )
        st.page_link("pages/CodingPath.py", label="Open coding path", icon="💻")

st.divider()
st.subheader("Your progress")

try:
    token = st.session_state.access_token
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
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.bar_chart({row["topic"]: row["accuracy"] for row in rows})
else:
    st.info("Complete a quiz or coding level to see topic stats here.")

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
