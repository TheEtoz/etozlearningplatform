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


def _quiz_load_options():
    return (
        selectinload(Quiz.quiz_questions)
        .selectinload(QuizQuestion.question)
        .selectinload(Question.topic_tags)
    )


def list_quizzes(
    database: Session,
    *,
    actor_id: int | None = None,
) -> list[Quiz]:
    """Return quizzes visible to the actor (public + own private)."""

    from sqlalchemy import or_

    statement = (
        select(Quiz).options(_quiz_load_options()).order_by(Quiz.id)
    )
    if actor_id is not None:
        statement = statement.where(
            or_(
                Quiz.visibility == "public",
                Quiz.owner_id == actor_id,
                Quiz.owner_id.is_(None),
            )
        )
    return list(database.scalars(statement).unique().all())


def get_quiz(database: Session, quiz_id: int) -> Quiz | None:
    """Return one quiz with ordered questions and topics."""

    statement = (
        select(Quiz)
        .options(_quiz_load_options())
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
    *,
    class_id: int | None = None,
) -> dict[int, dict[str, object]]:
    """Return completion and score summaries keyed by quiz id."""

    statement = select(QuizAttempt).where(QuizAttempt.user_id == user_id)
    if class_id is not None:
        statement = statement.where(QuizAttempt.class_id == class_id)
    attempts = database.scalars(statement.order_by(QuizAttempt.id.desc())).all()

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


def create_quiz(
    database: Session,
    payload: QuizCreate,
    *,
    owner_id: int | None = None,
) -> Quiz:
    """Create an empty quiz shell for the teacher to populate."""

    title = payload.title.strip()
    visibility = (
        payload.visibility.value
        if hasattr(payload.visibility, "value")
        else (payload.visibility or "private")
    )
    if owner_id is not None:
        existing = database.scalars(
            select(Quiz).where(
                Quiz.title == title,
                Quiz.owner_id == owner_id,
            )
        ).first()
        if existing is not None:
            raise QuizServiceError("You already have a quiz with this title")

    quiz = Quiz(
        title=title,
        description=(payload.description or "").strip(),
        topic=None,
        is_timed=payload.is_timed,
        duration_seconds=payload.duration_seconds,
        owner_id=owner_id,
        visibility=visibility,
    )
    database.add(quiz)
    database.commit()
    refreshed = get_quiz(database, quiz.id)
    if refreshed is None:
        raise QuizServiceError("Quiz not found after create")
    return refreshed


def update_quiz(
    database: Session,
    quiz_id: int,
    payload: QuizUpdate,
    *,
    actor_id: int | None = None,
) -> Quiz:
    """Update quiz metadata."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")
    if (
        actor_id is not None
        and quiz.owner_id is not None
        and quiz.owner_id != actor_id
    ):
        raise QuizServiceError("Only the author can edit this quiz")

    data = payload.model_dump(exclude_unset=True)
    if "visibility" in data and data["visibility"] is not None:
        data["visibility"] = data["visibility"].value
    if "title" in data and data["title"] is not None:
        title = str(data["title"]).strip()
        data["title"] = title
        if quiz.owner_id is not None:
            existing = database.query(Quiz).filter(
                Quiz.owner_id == quiz.owner_id,
                Quiz.title == title,
                Quiz.id != quiz.id,
            ).first()
            if existing is not None:
                raise QuizServiceError("You already have a quiz with this title")
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


def delete_quiz(
    database: Session,
    quiz_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    """Delete a quiz and its membership rows."""

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")
    if (
        actor_id is not None
        and quiz.owner_id is not None
        and quiz.owner_id != actor_id
    ):
        raise QuizServiceError("Only the author can delete this quiz")
    database.delete(quiz)
    database.commit()


def clone_quiz(
    database: Session,
    quiz_id: int,
    *,
    owner_id: int,
    title_suffix: str = " (copy)",
) -> Quiz:
    """Deep-copy a quiz and its questions as private copies for the actor."""

    from backend.services.question_service import (
        QuestionServiceError,
        clone_question,
    )

    source = get_quiz(database, quiz_id)
    if source is None:
        raise QuizServiceError("Quiz not found")
    if source.visibility == "private" and source.owner_id not in (None, owner_id):
        raise QuizServiceError("Cannot import a private quiz you do not own")

    title = (source.title + title_suffix)[:200]
    # Ensure unique title for this owner
    base = title
    counter = 2
    while database.scalars(
        select(Quiz).where(Quiz.owner_id == owner_id, Quiz.title == title)
    ).first():
        title = f"{base[:190]} {counter}"
        counter += 1

    clone = Quiz(
        title=title,
        description=source.description or "",
        topic=source.topic,
        is_timed=source.is_timed,
        duration_seconds=source.duration_seconds,
        owner_id=owner_id,
        visibility="private",
        source_quiz_id=source.id,
    )
    database.add(clone)
    database.flush()

    for position, link in enumerate(source.quiz_questions):
        try:
            question_copy = clone_question(
                database,
                link.question_id,
                owner_id=owner_id,
                title_suffix=" (copy)",
                commit=False,
            )
        except QuestionServiceError as error:
            database.rollback()
            raise QuizServiceError(str(error)) from error
        database.add(
            QuizQuestion(
                quiz_id=clone.id,
                question_id=question_copy.id,
                position=position,
            )
        )
    database.commit()
    refreshed = get_quiz(database, clone.id)
    if refreshed is None:
        raise QuizServiceError("Clone failed")
    return refreshed


def quiz_to_admin_dict(quiz: Quiz, *, actor_id: int | None = None) -> dict:
    is_owner = actor_id is not None and quiz.owner_id == actor_id
    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "is_timed": quiz.is_timed,
        "duration_seconds": quiz.duration_seconds,
        "question_ids": [link.question_id for link in quiz.quiz_questions],
        "topics": quiz_topics(quiz),
        "owner_id": quiz.owner_id,
        "visibility": quiz.visibility or "public",
        "source_quiz_id": quiz.source_quiz_id,
        "can_edit": is_owner or quiz.owner_id is None,
        "can_delete": is_owner,
    }


def actor_can_use_quiz(quiz: Quiz, actor_id: int) -> bool:
    """Teachers may publish public/legacy quizzes or their own private ones."""

    if quiz.visibility != "private":
        return True
    return quiz.owner_id in (None, actor_id)


def set_quiz_questions(
    database: Session,
    quiz_id: int,
    question_ids: list[int],
    *,
    actor_id: int | None = None,
) -> Quiz:
    """Replace ordered quiz membership with the given bank question ids."""

    from backend.services.question_service import actor_can_use_question

    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise QuizServiceError("Quiz not found")

    if len(question_ids) != len(set(question_ids)):
        raise QuizServiceError("Duplicate question ids are not allowed")

    for question_id in question_ids:
        question = database.get(Question, question_id)
        if question is None:
            raise QuizServiceError(f"Question {question_id} not found")
        if actor_id is not None and not actor_can_use_question(question, actor_id):
            raise QuizServiceError(
                f"Cannot attach private question {question_id} you do not own"
            )

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
    class_id: int | None = None,
    persist: bool = True,
) -> dict[str, object] | None:
    """Grade mixed MCQ/coding quiz.

    When ``persist`` is False (public demo), return the score/review without
    writing submissions, attempts, or topic progress.
    """

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
                if persist:
                    database.add(
                        Submission(
                            user_id=user_id,
                            question_id=question.id,
                            class_id=class_id,
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
                if persist:
                    database.add(
                        Submission(
                            user_id=user_id,
                            question_id=question.id,
                            class_id=class_id,
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

    if not persist:
        return {
            "quiz_id": quiz.id,
            "attempt_id": 0,
            "questions_total": total,
            "questions_answered": answered,
            "questions_correct": correct,
            "score": score_value,
            "is_completed": True,
            "results": results,
        }

    attempt = QuizAttempt(
        user_id=user_id,
        quiz_id=quiz.id,
        class_id=class_id,
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
