"""Student quizzes — equal-size cards and mixed MCQ/coding player."""

import importlib
import random
import runpy
import time
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
    complete_quiz,
    get_quiz_questions,
    list_quizzes,
    run_code,
)
from frontend.utils.guards import require_student
from frontend.utils.session import get_access_token, init_session_state
from frontend.utils.ui import render_preserved_text

st.set_page_config(page_title="Practice | ETOZ", page_icon="🧠", layout="wide")
init_session_state()
require_student()

st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 280px;
        height: 100%;
    }
    .quiz-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.4rem 0;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        min-height: 2.6rem;
    }
    .quiz-card-desc {
        color: #475569;
        font-size: 0.92rem;
        white-space: pre-wrap;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        min-height: 3.6rem;
        margin-bottom: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_quiz_state() -> None:
    defaults = {
        "quiz_started": False,
        "quiz_finished": False,
        "quiz_index": 0,
        "quiz_answers": {},
        "quiz_codes": {},
        "shuffled_choices": {},
        "quiz_questions": [],
        "active_quiz": None,
        "quiz_started_at": None,
        "quiz_results": None,
        "catalog_search": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_quiz() -> None:
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.session_state.quiz_index = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_codes = {}
    st.session_state.shuffled_choices = {}
    st.session_state.quiz_questions = []
    st.session_state.active_quiz = None
    st.session_state.quiz_started_at = None
    st.session_state.quiz_results = None


def start_quiz(quiz: dict, questions: list[dict]) -> None:
    st.session_state.quiz_started = True
    st.session_state.quiz_finished = False
    st.session_state.quiz_index = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_codes = {}
    st.session_state.shuffled_choices = {}
    st.session_state.quiz_questions = questions
    st.session_state.active_quiz = quiz
    st.session_state.quiz_started_at = time.time()
    st.session_state.quiz_results = None
    for question in questions:
        if question.get("type") == "coding":
            st.session_state.quiz_codes[str(question["id"])] = (
                question.get("starter_code") or ""
            )


def finish_and_reveal() -> None:
    quiz = st.session_state.active_quiz
    answers = []
    for question in st.session_state.quiz_questions:
        qid = question["id"]
        item = {"question_id": qid, "answer": None, "code": None}
        if question.get("type") == "coding":
            item["code"] = st.session_state.quiz_codes.get(str(qid))
        else:
            item["answer"] = st.session_state.quiz_answers.get(str(qid))
        answers.append(item)
    try:
        results = complete_quiz(get_access_token(), quiz["id"], answers)
    except APIError as error:
        st.error(str(error))
        return
    st.session_state.quiz_results = results
    st.session_state.quiz_finished = True


@st.fragment(run_every=1.0)
def render_timer() -> None:
    quiz = st.session_state.active_quiz
    if (
        quiz is None
        or not quiz.get("is_timed")
        or st.session_state.quiz_finished
        or st.session_state.quiz_started_at is None
    ):
        return
    duration = quiz.get("duration_seconds") or 0
    remaining = max(0, duration - int(time.time() - st.session_state.quiz_started_at))
    minutes, seconds = divmod(remaining, 60)
    st.metric("Time left", f"{minutes:02d}:{seconds:02d}")
    if remaining == 0:
        finish_and_reveal()
        st.rerun()


def render_catalog() -> None:
    st.title("Practice Quizzes")
    st.page_link("pages/Dashboard.py", label="Back to Dashboard", icon="📊")
    st.session_state.catalog_search = st.text_input(
        "Search",
        value=st.session_state.catalog_search,
        placeholder="Filter by title or topic",
    )
    try:
        quizzes = list_quizzes(get_access_token())
    except APIError as error:
        st.error(str(error))
        return

    needle = st.session_state.catalog_search.strip().lower()
    if needle:
        quizzes = [
            quiz
            for quiz in quizzes
            if needle in quiz["title"].lower()
            or needle in quiz.get("description", "").lower()
            or any(needle in topic.lower() for topic in quiz.get("topics") or [])
        ]

    if not quizzes:
        st.info("No quizzes match your search.")
        return

    cols = st.columns(3)
    for index, quiz in enumerate(quizzes):
        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(
                    f'<p class="quiz-card-title">{quiz["title"]}</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<p class="quiz-card-desc">{quiz.get("description") or ""}</p>',
                    unsafe_allow_html=True,
                )
                topics = ", ".join(quiz.get("topics") or []) or "mixed"
                types = "/".join(quiz.get("question_types") or [])
                timing = (
                    f"Timed · {quiz.get('duration_seconds')}s"
                    if quiz.get("is_timed")
                    else "Untimed"
                )
                st.caption(
                    f"{timing} · {quiz.get('question_count', 0)} Q · {types} · {topics}"
                )
                if quiz.get("is_completed"):
                    st.success(
                        f"Done · best {quiz.get('best_score')} · "
                        f"last {quiz.get('last_score')}"
                    )
                    label = "Redo quiz"
                else:
                    st.caption("Not completed yet")
                    label = "Start quiz"
                if st.button(label, key=f"start_{quiz['id']}", use_container_width=True):
                    try:
                        questions = get_quiz_questions(get_access_token(), quiz["id"])
                    except APIError as error:
                        st.error(str(error))
                        return
                    start_quiz(quiz, questions)
                    st.rerun()


def render_player() -> None:
    quiz = st.session_state.active_quiz
    questions = st.session_state.quiz_questions
    index = st.session_state.quiz_index
    question = questions[index]

    top1, top2, top3 = st.columns([1, 2, 1])
    with top1:
        if st.button("Finish quiz", type="primary"):
            finish_and_reveal()
            st.rerun()
    with top2:
        st.subheader(quiz["title"])
        st.caption(f"Question {index + 1} of {len(questions)}")
    with top3:
        if st.button("Leave quiz"):
            reset_quiz()
            st.rerun()
        render_timer()

    if st.session_state.quiz_finished and st.session_state.quiz_results:
        results = st.session_state.quiz_results
        st.success(
            f"Score {results['score']} · "
            f"{results['questions_correct']}/{results['questions_total']} correct"
        )
        for item in results.get("results") or []:
            mark = "✅" if item.get("is_correct") else "❌"
            st.markdown(f"{mark} **{item['title']}** ({item.get('type')})")
            if item.get("type") == "mcq":
                st.write(
                    f"Your answer: {item.get('selected_answer') or '(skipped)'} · "
                    f"Correct: {item.get('correct_answer')}"
                )
            else:
                st.write(
                    f"Coding score: {item.get('score')} · "
                    f"{'Passed' if item.get('is_correct') else 'Not passed'}"
                )
        if st.button("Back to catalog"):
            reset_quiz()
            st.rerun()
        return

    nav, body = st.columns([1, 3])
    with nav:
        st.caption("Questions")
        for i, item in enumerate(questions):
            answered = (
                str(item["id"]) in st.session_state.quiz_codes
                if item.get("type") == "coding"
                else str(item["id"]) in st.session_state.quiz_answers
            )
            prefix = "●" if answered else "○"
            if st.button(
                f"{prefix} {i + 1}. {item['type']}",
                key=f"nav_{i}",
                use_container_width=True,
            ):
                st.session_state.quiz_index = i
                st.rerun()

    with body:
        st.markdown(f"### {question['title']}")
        render_preserved_text(question.get("description") or "")
        st.caption(
            f"{question.get('difficulty')} · "
            f"{', '.join(question.get('topics') or [])}"
        )

        if question.get("type") == "coding":
            key = f"code_{question['id']}"
            if key not in st.session_state:
                st.session_state[key] = st.session_state.quiz_codes.get(
                    str(question["id"]),
                    question.get("starter_code") or "",
                )
            st.text_area("Your code", height=220, key=key)
            st.session_state.quiz_codes[str(question["id"])] = st.session_state[key]
            if st.button("Run (sandbox)", key=f"run_{question['id']}"):
                try:
                    output = run_code(get_access_token(), st.session_state[key])
                    st.code(output.get("stdout") or "(no stdout)", language="text")
                    if output.get("stderr"):
                        st.error(output["stderr"])
                except APIError as error:
                    st.error(str(error))
        else:
            choices = question.get("choices") or []
            qid = str(question["id"])
            if qid not in st.session_state.shuffled_choices:
                shuffled = choices[:]
                random.Random(quiz["id"] * 1000 + question["id"]).shuffle(shuffled)
                st.session_state.shuffled_choices[qid] = shuffled
            selected = st.radio(
                "Choose one",
                st.session_state.shuffled_choices[qid],
                index=(
                    st.session_state.shuffled_choices[qid].index(
                        st.session_state.quiz_answers[qid]
                    )
                    if qid in st.session_state.quiz_answers
                    and st.session_state.quiz_answers[qid]
                    in st.session_state.shuffled_choices[qid]
                    else None
                ),
                key=f"mcq_{question['id']}",
            )
            if selected is not None:
                st.session_state.quiz_answers[qid] = selected

        prev_col, next_col = st.columns(2)
        with prev_col:
            if st.button("Previous", disabled=index == 0):
                st.session_state.quiz_index = index - 1
                st.rerun()
        with next_col:
            if st.button("Next", disabled=index >= len(questions) - 1):
                st.session_state.quiz_index = index + 1
                st.rerun()


initialize_quiz_state()
if st.session_state.quiz_started:
    render_player()
else:
    render_catalog()
