"""Shared test helpers for bank questions and quiz membership."""

from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_question import QuizQuestion
from backend.models.topic import Topic


def ensure_topic(database_session, name: str) -> Topic:
    topic = (
        database_session.query(Topic).filter(Topic.name == name).one_or_none()
    )
    if topic is None:
        topic = Topic(name=name)
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
    topics: list[str] | None = None,
    choices: list[str] | None = None,
    correct_answer: str | None = None,
    starter_code: str | None = None,
    test_cases: list | None = None,
) -> Question:
    topic_names = topics or ["basics"]
    tags = [ensure_topic(database_session, name) for name in topic_names]
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
