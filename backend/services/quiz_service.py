"""Quiz catalog, membership, mixed grading, and student attempts."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_attempt import QuizAttempt
from backend.models.quiz_question import QuizQuestion
from backend.models.submission import Submission
from backend.schemas.quiz import QuizCreate, QuizUpdate
from backend.services.docker_service import DockerExecutionError, grade_python_code
from backend.services.progress_service import record_topic_attempt


class QuizServiceError(ValueError):
    """Raised for quiz admin/student operations that cannot complete."""


def list_quizzes(database: Session) -> list[Quiz]:
    """Return quizzes with ordered membership and topic tags loaded."""

    statement = (
        select(Quiz)
        .options(
            selectinload(Quiz.quiz_questions)
            .selectinload(QuizQuestion.question)
            .selectinload(Question.topic_tags)
        )
        .order_by(Quiz.id)
    )
    return list(database.scalars(statement).unique().all())


def get_quiz(database: Session, quiz_id: int) -> Quiz | None:
    """Return one quiz with ordered questions and topics."""

    statement = (
        select(Quiz)
        .options(
            selectinload(Quiz.quiz_questions)
            .selectinload(QuizQuestion.question)
            .selectinload(Question.topic_tags)
        )
        .where(Quiz.id == quiz_id)
    )
    return database.scalars(statement).unique().first()


def get_quiz_questions(database: Session, quiz_id: int) -> list[Question]:
    """Return ordered bank questions belonging to a quiz."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        return []
    return list(quiz.questions)


def quiz_topics(quiz: Quiz) -> list[str]:
    """Union of topics across all questions in the quiz."""

    names: set[str] = set()
    for question in quiz.questions:
        names.update(question.topics)
    return sorted(names)


def get_student_quiz_stats(
    database: Session,
    user_id: int,
) -> dict[int, dict[str, object]]:
    """Return completion and score summaries keyed by quiz id."""

    attempts = database.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user_id)
        .order_by(QuizAttempt.id.desc())
    ).all()

    stats: dict[int, dict[str, object]] = {}
    for attempt in attempts:
        current = stats.get(attempt.quiz_id)
        if current is None:
            stats[attempt.quiz_id] = {
                "is_completed": True,
                "attempt_count": 1,
                "best_score": attempt.score,
                "last_score": attempt.score,
            }
            continue
        current["attempt_count"] = int(current["attempt_count"]) + 1
        if attempt.score > current["best_score"]:
            current["best_score"] = attempt.score
    return stats


def create_quiz(database: Session, payload: QuizCreate) -> Quiz:
    """Create an empty quiz shell for the teacher to populate."""

    existing = database.scalars(
        select(Quiz).where(Quiz.title == payload.title.strip())
    ).first()
    if existing is not None:
        raise QuizServiceError("A quiz with this title already exists")

    quiz = Quiz(
        title=payload.title.strip(),
        description=payload.description.strip(),
        topic=None,
        is_timed=payload.is_timed,
        duration_seconds=payload.duration_seconds,
    )
    database.add(quiz)
    database.commit()
    refreshed = get_quiz(database, quiz.id)
    if refreshed is None:
        raise QuizServiceError("Quiz not found after create")
    return refreshed


def update_quiz(database: Session, quiz_id: int, payload: QuizUpdate) -> Quiz:
    """Update quiz metadata."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")

    data = payload.model_dump(exclude_unset=True)
    if "is_timed" in data or "duration_seconds" in data:
        is_timed = data.get("is_timed", quiz.is_timed)
        duration = data.get("duration_seconds", quiz.duration_seconds)
        if is_timed and not duration:
            raise QuizServiceError("Timed quizzes require duration_seconds")
        if not is_timed:
            data["duration_seconds"] = None

    for field, value in data.items():
        setattr(quiz, field, value)

    database.commit()
    refreshed = get_quiz(database, quiz_id)
    if refreshed is None:
        raise QuizServiceError("Quiz not found")
    return refreshed


def delete_quiz(database: Session, quiz_id: int) -> None:
    """Delete a quiz and its membership rows."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")
    database.delete(quiz)
    database.commit()


def set_quiz_questions(
    database: Session,
    quiz_id: int,
    question_ids: list[int],
) -> Quiz:
    """Replace ordered quiz membership with the given bank question ids."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")

    if len(question_ids) != len(set(question_ids)):
        raise QuizServiceError("Duplicate question ids are not allowed")

    for question_id in question_ids:
        question = database.get(Question, question_id)
        if question is None:
            raise QuizServiceError(f"Question {question_id} not found")

    for link in list(quiz.quiz_questions):
        database.delete(link)
    database.flush()
    for position, question_id in enumerate(question_ids):
        database.add(
            QuizQuestion(
                quiz_id=quiz.id,
                question_id=question_id,
                position=position,
            )
        )
    database.commit()
    database.expire_all()
    refreshed = get_quiz(database, quiz_id)
    if refreshed is None:
        raise QuizServiceError("Quiz not found")
    return refreshed


def _grade_coding_inline(question: Question, code: str) -> tuple[int, bool, str]:
    """Grade coding inside a quiz; return score, passed, detail."""

    try:
        result = grade_python_code(code, list(question.test_cases or []))
    except DockerExecutionError as error:
        return 0, False, str(error)

    if result.tests_total == 0 or result.timed_out or result.mode == "error":
        return 0, False, result.stderr or "Grading error"
    score = int(round((result.tests_passed / result.tests_total) * 100))
    return score, score == 100, ""


def complete_quiz(
    database: Session,
    *,
    user_id: int,
    quiz_id: int,
    answers: dict[int, dict[str, str | None]],
) -> dict[str, object] | None:
    """Grade mixed MCQ/coding quiz, persist attempt, update per-topic progress."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        return None

    results = []
    answered = 0
    correct = 0
    topic_attempted: dict[str, int] = {}
    topic_correct: dict[str, int] = {}

    for question in quiz.questions:
        payload = answers.get(question.id, {})
        selected = (payload.get("answer") or "").strip() or None
        code = (payload.get("code") or "").strip() or None
        is_correct = False
        score = 0
        skipped = False
        detail = ""

        if question.type == "mcq":
            skipped = not selected
            correct_answer = (question.correct_answer or "").strip()
            is_correct = (not skipped) and selected == correct_answer
            score = 100 if is_correct else 0
            if not skipped:
                answered += 1
                database.add(
                    Submission(
                        user_id=user_id,
                        question_id=question.id,
                        answer=selected,
                        score=score,
                        status="passed" if is_correct else "failed",
                    )
                )
            results.append(
                {
                    "question_id": question.id,
                    "title": question.title,
                    "description": question.description,
                    "type": "mcq",
                    "selected_answer": selected,
                    "submitted_code": None,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "skipped": skipped,
                    "score": score,
                }
            )
        else:
            skipped = not code
            if skipped:
                results.append(
                    {
                        "question_id": question.id,
                        "title": question.title,
                        "description": question.description,
                        "type": "coding",
                        "selected_answer": None,
                        "submitted_code": None,
                        "correct_answer": None,
                        "is_correct": False,
                        "skipped": True,
                        "score": 0,
                    }
                )
            else:
                answered += 1
                score, is_correct, detail = _grade_coding_inline(question, code)
                database.add(
                    Submission(
                        user_id=user_id,
                        question_id=question.id,
                        code=code,
                        score=score,
                        status=(
                            "passed"
                            if is_correct
                            else ("error" if detail and score == 0 else "failed")
                        ),
                    )
                )
                results.append(
                    {
                        "question_id": question.id,
                        "title": question.title,
                        "description": question.description,
                        "type": "coding",
                        "selected_answer": None,
                        "submitted_code": code,
                        "correct_answer": None,
                        "is_correct": is_correct,
                        "skipped": False,
                        "score": score,
                    }
                )

        if is_correct:
            correct += 1

        if not skipped:
            for topic_name in question.topics or ["general"]:
                topic_attempted[topic_name] = topic_attempted.get(topic_name, 0) + 1
                if is_correct:
                    topic_correct[topic_name] = topic_correct.get(topic_name, 0) + 1

    total = len(quiz.questions)
    score_value = (
        (Decimal(correct) * Decimal("100") / Decimal(total)).quantize(
            Decimal("0.01")
        )
        if total
        else Decimal("0.00")
    )

    attempt = QuizAttempt(
        user_id=user_id,
        quiz_id=quiz.id,
        questions_total=total,
        questions_answered=answered,
        questions_correct=correct,
        score=score_value,
        status="completed",
    )
    database.add(attempt)

    for topic_name, attempted_count in topic_attempted.items():
        record_topic_attempt(
            database,
            user_id=user_id,
            topic=topic_name,
            questions_attempted=attempted_count,
            questions_correct=topic_correct.get(topic_name, 0),
        )

    database.commit()
    database.refresh(attempt)

    return {
        "quiz_id": quiz.id,
        "attempt_id": attempt.id,
        "questions_total": total,
        "questions_answered": answered,
        "questions_correct": correct,
        "score": score_value,
        "is_completed": True,
        "results": results,
    }
