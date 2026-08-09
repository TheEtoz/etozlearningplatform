"""Seed topics, question bank, mixed quizzes, coding path, and demo classes."""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.classroom import ClassModule, ClassQuiz, Classroom
from backend.models.coding_module import CodingModule, ModuleBlock
from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_question import QuizQuestion
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.security import hash_password

SUBJECT_NAMES = ["python", "math", "java"]

# Areas seeded under the python subject
TOPIC_NAMES = [
    "basics",
    "operators",
    "data types",
    "lists",
    "loops",
    "functions",
    "dictionaries",
]

BANK_QUESTIONS = [
    {
        "title": "Adding integers",
        "description": "What is printed by `print(2 + 3)`?",
        "difficulty": "easy",
        "type": "mcq",
        "topics": ["operators", "basics"],
        "choices": ["4", "5", "23", "Error"],
        "correct_answer": "5",
    },
    {
        "title": "Python variable type",
        "description": 'What type is the value created by `name = "Ada"`?',
        "difficulty": "easy",
        "type": "mcq",
        "topics": ["data types", "basics"],
        "choices": ["int", "str", "list", "bool"],
        "correct_answer": "str",
    },
    {
        "title": "List indexing",
        "description": "What does `[10, 20, 30][0]` return?",
        "difficulty": "easy",
        "type": "mcq",
        "topics": ["lists"],
        "choices": ["0", "10", "20", "30"],
        "correct_answer": "10",
    },
    {
        "title": "Range in a loop",
        "description": "How many times does `for i in range(3):` run?",
        "difficulty": "easy",
        "type": "mcq",
        "topics": ["loops"],
        "choices": ["2", "3", "4", "It never stops"],
        "correct_answer": "3",
    },
    {
        "title": "Function return value",
        "description": (
            "What does a Python function return when it has no "
            "`return` statement?"
        ),
        "difficulty": "medium",
        "type": "mcq",
        "topics": ["functions"],
        "choices": ["0", "False", "None", "An empty string"],
        "correct_answer": "None",
    },
    {
        "title": "Dictionary lookup",
        "description": 'What is `{"language": "Python"}["language"]`?',
        "difficulty": "medium",
        "type": "mcq",
        "topics": ["dictionaries"],
        "choices": ["language", "Python", "KeyError", "None"],
        "correct_answer": "Python",
    },
    {
        "title": "Hello, World!",
        "description": "Write a program that prints exactly: `Hello, World!`",
        "difficulty": "easy",
        "type": "coding",
        "topics": ["basics"],
        "starter_code": 'print("Hello, World!")\n',
        "test_cases": [{"stdin": "", "expected_stdout": "Hello, World!"}],
    },
    {
        "title": "Add two numbers",
        "description": (
            "Read two integers (each on its own line) and print their sum."
        ),
        "difficulty": "easy",
        "type": "coding",
        "topics": ["operators", "basics"],
        "starter_code": "a = int(input())\nb = int(input())\nprint(a + b)\n",
        "test_cases": [
            {"stdin": "2\n3\n", "expected_stdout": "5"},
            {"stdin": "10\n-4\n", "expected_stdout": "6"},
        ],
    },
    {
        "title": "Count up to N",
        "description": (
            "Read N and print numbers from 1 to N, each on its own line."
        ),
        "difficulty": "medium",
        "type": "coding",
        "topics": ["loops"],
        "starter_code": (
            "n = int(input())\n"
            "for i in range(1, n + 1):\n"
            "    print(i)\n"
        ),
        "test_cases": [
            {"stdin": "1\n", "expected_stdout": "1"},
            {"stdin": "3\n", "expected_stdout": "1\n2\n3"},
        ],
    },
]

QUIZZES = [
    {
        "title": "Python Warm-up Mix",
        "description": "A mixed quiz with MCQ and a short coding task.",
        "is_timed": False,
        "duration_seconds": None,
        "question_titles": [
            "Adding integers",
            "Python variable type",
            "Hello, World!",
        ],
    },
    {
        "title": "Lists & Loops Sprint",
        "description": "Timed check on lists and loops.",
        "is_timed": True,
        "duration_seconds": 120,
        "question_titles": ["List indexing", "Range in a loop"],
    },
    {
        "title": "Functions & Dicts",
        "description": "Untimed review of functions and dictionaries.",
        "is_timed": False,
        "duration_seconds": None,
        "question_titles": ["Function return value", "Dictionary lookup"],
    },
]

PATH_MODULES = [
    {
        "title": "Module 1 - Basics",
        "description": "Start here with print and simple arithmetic.",
        "position": 0,
        "difficulty_label": "Beginner",
        "levels": ["Hello, World!", "Add two numbers"],
    },
    {
        "title": "Module 2 - Loops",
        "description": "Practice looping patterns.",
        "position": 1,
        "difficulty_label": "Intermediate",
        "levels": ["Count up to N"],
    },
]


def _get_or_create_subject(database: Session, name: str) -> Subject:
    subject = database.scalars(select(Subject).where(Subject.name == name)).first()
    if subject is None:
        subject = Subject(name=name)
        database.add(subject)
        database.flush()
    return subject


def _get_or_create_topic(
    database: Session,
    name: str,
    *,
    subject: Subject,
) -> Topic:
    topic = database.scalars(
        select(Topic).where(
            Topic.name == name,
            Topic.subject_id == subject.id,
        )
    ).first()
    if topic is None:
        topic = Topic(name=name, subject_id=subject.id)
        database.add(topic)
        database.flush()
    return topic


def _get_question(database: Session, title: str) -> Question | None:
    return database.scalars(select(Question).where(Question.title == title)).first()


def seed_all() -> dict[str, int]:
    """Insert missing seed data and return creation counts."""

    counts = {
        "subjects": 0,
        "topics": 0,
        "questions": 0,
        "quizzes": 0,
        "quiz_links": 0,
        "modules": 0,
        "levels": 0,
        "classes": 0,
        "teachers": 0,
    }

    with SessionLocal() as database:
        for name in SUBJECT_NAMES:
            existing = database.scalars(
                select(Subject).where(Subject.name == name)
            ).first()
            if existing is None:
                database.add(Subject(name=name))
                database.flush()
                counts["subjects"] += 1

        python = _get_or_create_subject(database, "python")
        topic_map: dict[str, Topic] = {}
        for name in TOPIC_NAMES:
            existing = database.scalars(
                select(Topic).where(
                    Topic.name == name,
                    Topic.subject_id == python.id,
                )
            ).first()
            if existing is None:
                topic = Topic(name=name, subject_id=python.id)
                database.add(topic)
                database.flush()
                counts["topics"] += 1
                topic_map[name] = topic
            else:
                topic_map[name] = existing

        question_map: dict[str, Question] = {}
        for raw in BANK_QUESTIONS:
            existing = _get_question(database, raw["title"])
            if existing is None:
                question = Question(
                    title=raw["title"],
                    description=raw["description"],
                    difficulty=raw["difficulty"],
                    type=raw["type"],
                    topic=raw["topics"][0],
                    language="python",
                    choices=raw.get("choices"),
                    correct_answer=raw.get("correct_answer"),
                    starter_code=raw.get("starter_code"),
                    test_cases=raw.get("test_cases"),
                )
                for topic_name in raw["topics"]:
                    question.topic_tags.append(
                        topic_map.get(topic_name)
                        or _get_or_create_topic(
                            database, topic_name, subject=python
                        )
                    )
                database.add(question)
                database.flush()
                counts["questions"] += 1
                question_map[raw["title"]] = question
            else:
                if not existing.topic_tags:
                    for topic_name in raw["topics"]:
                        existing.topic_tags.append(
                            topic_map.get(topic_name)
                            or _get_or_create_topic(
                                database, topic_name, subject=python
                            )
                        )
                question_map[raw["title"]] = existing

        teacher = database.scalars(
            select(User).where(User.username == "demo_teacher")
        ).first()
        if teacher is None:
            teacher = User(
                username="demo_teacher",
                email="demo_teacher@example.com",
                hashed_password=hash_password("password123"),
                role="admin",
                email_verified=True,
            )
            database.add(teacher)
            database.flush()
            counts["teachers"] += 1
        else:
            if teacher.role != "admin":
                teacher.role = "admin"
            if not teacher.email_verified:
                teacher.email_verified = True
            # EmailStr rejects reserved TLDs like .local
            if teacher.email.endswith(".local"):
                teacher.email = "demo_teacher@example.com"

        for quiz_data in QUIZZES:
            quiz = database.scalars(
                select(Quiz).where(
                    Quiz.title == quiz_data["title"],
                    Quiz.owner_id == teacher.id,
                )
            ).first()
            if quiz is None:
                quiz = Quiz(
                    title=quiz_data["title"],
                    description=quiz_data["description"],
                    topic=None,
                    is_timed=quiz_data["is_timed"],
                    duration_seconds=quiz_data["duration_seconds"],
                    owner_id=teacher.id,
                    visibility="public",
                )
                database.add(quiz)
                database.flush()
                counts["quizzes"] += 1
            else:
                quiz.owner_id = teacher.id
                quiz.visibility = quiz.visibility or "public"

            existing_links = {
                link.question_id: link for link in quiz.quiz_questions
            }
            for position, title in enumerate(quiz_data["question_titles"]):
                question = question_map[title]
                if question.id in existing_links:
                    existing_links[question.id].position = position
                else:
                    database.add(
                        QuizQuestion(
                            quiz_id=quiz.id,
                            question_id=question.id,
                            position=position,
                        )
                    )
                    counts["quiz_links"] += 1

        quiz_ids = [
            quiz.id
            for quiz in database.scalars(select(Quiz).order_by(Quiz.id)).all()
        ]

        demo_classes = [
            {
                "title": "Intro Python (Public)",
                "description": (
                    "Open demo class for schools. Students can browse and enroll "
                    "without a code."
                ),
                "visibility": "public",
                "enrollment_code": "PUBLIC01",
                "quiz_ids": quiz_ids[:2] if quiz_ids else [],
                "module_slice": slice(0, 1),
            },
            {
                "title": "Cohort A (Private)",
                "description": (
                    "Private demo class. Students join only with the enrollment code."
                ),
                "visibility": "private",
                "enrollment_code": "PRIVATE1",
                "quiz_ids": quiz_ids[:1] if quiz_ids else [],
                "module_slice": slice(0, 2),
            },
        ]

        class_rows: list[Classroom] = []
        for class_data in demo_classes:
            classroom = database.scalars(
                select(Classroom).where(Classroom.title == class_data["title"])
            ).first()
            if classroom is None:
                classroom = Classroom(
                    title=class_data["title"],
                    description=class_data["description"],
                    owner_id=teacher.id,
                    visibility=class_data["visibility"],
                    enrollment_code=class_data["enrollment_code"],
                    is_active=True,
                )
                database.add(classroom)
                database.flush()
                counts["classes"] += 1
            class_rows.append(classroom)

            existing_quiz_links = {
                link.quiz_id: link for link in classroom.class_quizzes
            }
            for position, quiz_id in enumerate(class_data["quiz_ids"]):
                if quiz_id in existing_quiz_links:
                    existing_quiz_links[quiz_id].position = position
                    existing_quiz_links[quiz_id].is_published = True
                else:
                    database.add(
                        ClassQuiz(
                            class_id=classroom.id,
                            quiz_id=quiz_id,
                            position=position,
                            is_published=True,
                        )
                    )

        # Modules belong to a class — seed into the public demo class primarily.
        primary_class = class_rows[0] if class_rows else None
        if primary_class is not None:
            for module_data in PATH_MODULES:
                module = database.scalars(
                    select(CodingModule).where(
                        CodingModule.class_id == primary_class.id,
                        CodingModule.title == module_data["title"],
                    )
                ).first()
                if module is None:
                    module = CodingModule(
                        class_id=primary_class.id,
                        title=module_data["title"],
                        description=module_data["description"],
                        position=module_data["position"],
                        difficulty_label=module_data["difficulty_label"],
                    )
                    database.add(module)
                    database.flush()
                    counts["modules"] += 1
                    database.add(
                        ClassModule(
                            class_id=primary_class.id,
                            module_id=module.id,
                            position=module_data["position"],
                            is_published=True,
                        )
                    )

                if not module.blocks and module.description:
                    database.add(
                        ModuleBlock(
                            module_id=module.id,
                            position=0,
                            type="lecture",
                            payload={"markdown": module.description},
                        )
                    )
                existing_coding = {
                    block.question_id: block
                    for block in module.blocks
                    if block.type == "coding"
                }
                offset = 1 if module.description else 0
                for position, title in enumerate(module_data["levels"]):
                    question = question_map[title]
                    if question.id in existing_coding:
                        existing_coding[question.id].position = position + offset
                    else:
                        database.add(
                            ModuleBlock(
                                module_id=module.id,
                                position=position + offset,
                                type="coding",
                                payload={},
                                question_id=question.id,
                            )
                        )
                        counts["levels"] += 1

            # Copy first module into private class if missing.
            if len(class_rows) > 1 and PATH_MODULES:
                private = class_rows[1]
                first = PATH_MODULES[0]
                existing = database.scalars(
                    select(CodingModule).where(
                        CodingModule.class_id == private.id,
                        CodingModule.title == first["title"],
                    )
                ).first()
                if existing is None:
                    clone = CodingModule(
                        class_id=private.id,
                        title=first["title"],
                        description=first["description"],
                        position=0,
                        difficulty_label=first["difficulty_label"],
                    )
                    database.add(clone)
                    database.flush()
                    counts["modules"] += 1
                    database.add(
                        ClassModule(
                            class_id=private.id,
                            module_id=clone.id,
                            position=0,
                            is_published=True,
                        )
                    )
                    database.add(
                        ModuleBlock(
                            module_id=clone.id,
                            position=0,
                            type="lecture",
                            payload={"markdown": first["description"]},
                        )
                    )
                    for position, title in enumerate(first["levels"]):
                        database.add(
                            ModuleBlock(
                                module_id=clone.id,
                                position=position + 1,
                                type="coding",
                                payload={},
                                question_id=question_map[title].id,
                            )
                        )
                        counts["levels"] += 1

        database.commit()

    return counts


def seed_questions() -> tuple[int, int, int]:
    """Backward-compatible wrapper used by older docs/commands."""

    counts = seed_all()
    return counts["quizzes"], counts["questions"], counts["questions"]


def _refuse_demo_seed_in_production() -> None:
    env = (os.getenv("ETOZ_ENV") or os.getenv("ENVIRONMENT") or "").lower()
    allow = (os.getenv("ETOZ_SEED_DEMO") or "").lower() in {"1", "true", "yes"}
    if env in {"production", "prod"} and not allow:
        raise SystemExit(
            "Refusing to seed demo credentials in production. "
            "Use a non-production ETOZ_ENV, or set ETOZ_SEED_DEMO=1 only on "
            "dedicated demo hosts."
        )


if __name__ == "__main__":
    _refuse_demo_seed_in_production()
    result = seed_all()
    print(
        "Seed complete: "
        f"{result['subjects']} subjects, {result['topics']} areas, "
        f"{result['questions']} questions, "
        f"{result['quizzes']} quizzes, {result['quiz_links']} quiz links, "
        f"{result['modules']} modules, {result['levels']} levels, "
        f"{result['teachers']} teachers, {result['classes']} classes."
    )
    print(
        "Demo teacher login: demo_teacher / password123\n"
        "Public class code: PUBLIC01 · Private class code: PRIVATE1\n"
        "WARNING: never run this seed against a production database."
    )
