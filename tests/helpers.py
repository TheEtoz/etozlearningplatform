"""Shared test helpers for bank questions and quiz membership."""

from datetime import UTC, datetime

from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_question import QuizQuestion
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User


def mark_email_verified(database_session, username: str) -> None:
    """Mark a registered user as verified (tests skip the inbox)."""

    user = (
        database_session.query(User).filter(User.username == username).one_or_none()
    )
    assert user is not None, f"user {username!r} not found"
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    database_session.commit()


def register_and_login_headers(
    client,
    database_session,
    username: str,
    *,
    email: str | None = None,
    password: str = "password123",
) -> dict[str, str]:
    """Register, verify email in DB, log in, return Authorization header."""

    email = email or f"{username}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert register.status_code == 201, register.text
    mark_email_verified(database_session, username)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def ensure_subject(database_session, name: str = "python") -> Subject:
    subject = (
        database_session.query(Subject).filter(Subject.name == name).one_or_none()
    )
    if subject is None:
        subject = Subject(name=name)
        database_session.add(subject)
        database_session.flush()
    return subject


def ensure_topic(
    database_session,
    name: str,
    *,
    subject: str = "python",
) -> Topic:
    subject_row = ensure_subject(database_session, subject)
    topic = (
        database_session.query(Topic)
        .filter(Topic.name == name, Topic.subject_id == subject_row.id)
        .one_or_none()
    )
    if topic is None:
        topic = Topic(name=name, subject_id=subject_row.id)
        database_session.add(topic)
        database_session.flush()
    return topic


def make_question(
    database_session,
    *,
    title: str,
    description: str,
    difficulty: str = "easy",
    question_type: str = "mcq",
    subject: str = "python",
    topics: list[str] | None = None,
    choices: list[str] | None = None,
    correct_answer: str | None = None,
    starter_code: str | None = None,
    test_cases: list | None = None,
    owner_id: int | None = None,
    visibility: str = "public",
) -> Question:
    topic_names = topics or ["basics"]
    tags = [
        ensure_topic(database_session, name, subject=subject) for name in topic_names
    ]
    question = Question(
        title=title,
        description=description,
        difficulty=difficulty,
        type=question_type,
        topic=topic_names[0],
        choices=choices,
        correct_answer=correct_answer,
        starter_code=starter_code,
        test_cases=test_cases,
        topic_tags=tags,
        owner_id=owner_id,
        visibility=visibility,
    )
    database_session.add(question)
    database_session.flush()
    return question


def make_quiz_with_questions(
    database_session,
    *,
    title: str = "Operators Pack",
    description: str = "Beginner operators",
    is_timed: bool = False,
) -> Quiz:
    quiz = Quiz(
        title=title,
        description=description,
        topic=None,
        is_timed=is_timed,
        duration_seconds=60 if is_timed else None,
        visibility="public",
    )
    database_session.add(quiz)
    database_session.flush()

    q1 = make_question(
        database_session,
        title="Adding integers",
        description="2 + 3?",
        topics=["operators"],
        choices=["4", "5"],
        correct_answer="5",
    )
    q2 = make_question(
        database_session,
        title="Multiplying integers",
        description="2 * 3?",
        topics=["operators"],
        choices=["5", "6"],
        correct_answer="6",
    )
    database_session.add_all(
        [
            QuizQuestion(quiz_id=quiz.id, question_id=q1.id, position=0),
            QuizQuestion(quiz_id=quiz.id, question_id=q2.id, position=1),
        ]
    )
    database_session.commit()
    return quiz
