"""Seed topics, question bank, mixed quizzes, and coding path modules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.coding_module import CodingModule, ModuleLevel
from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_question import QuizQuestion
from backend.models.topic import Topic

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


def _get_or_create_topic(database: Session, name: str) -> Topic:
    topic = database.scalars(select(Topic).where(Topic.name == name)).first()
    if topic is None:
        topic = Topic(name=name)
        database.add(topic)
        database.flush()
    return topic


def _get_question(database: Session, title: str) -> Question | None:
    return database.scalars(select(Question).where(Question.title == title)).first()


def seed_all() -> dict[str, int]:
    """Insert missing seed data and return creation counts."""

    counts = {
        "topics": 0,
        "questions": 0,
        "quizzes": 0,
        "quiz_links": 0,
        "modules": 0,
        "levels": 0,
    }

    with SessionLocal() as database:
        topic_map: dict[str, Topic] = {}
        for name in TOPIC_NAMES:
            existing = database.scalars(
                select(Topic).where(Topic.name == name)
            ).first()
            if existing is None:
                topic = Topic(name=name)
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
                        or _get_or_create_topic(database, topic_name)
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
                            or _get_or_create_topic(database, topic_name)
                        )
                question_map[raw["title"]] = existing

        for quiz_data in QUIZZES:
            quiz = database.scalars(
                select(Quiz).where(Quiz.title == quiz_data["title"])
            ).first()
            if quiz is None:
                quiz = Quiz(
                    title=quiz_data["title"],
                    description=quiz_data["description"],
                    topic=None,
                    is_timed=quiz_data["is_timed"],
                    duration_seconds=quiz_data["duration_seconds"],
                )
                database.add(quiz)
                database.flush()
                counts["quizzes"] += 1

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

        for module_data in PATH_MODULES:
            module = database.scalars(
                select(CodingModule).where(
                    CodingModule.title == module_data["title"]
                )
            ).first()
            if module is None:
                module = CodingModule(
                    title=module_data["title"],
                    description=module_data["description"],
                    position=module_data["position"],
                    difficulty_label=module_data["difficulty_label"],
                )
                database.add(module)
                database.flush()
                counts["modules"] += 1

            existing_levels = {
                level.question_id: level for level in module.levels
            }
            for position, title in enumerate(module_data["levels"]):
                question = question_map[title]
                if question.id in existing_levels:
                    existing_levels[question.id].position = position
                else:
                    database.add(
                        ModuleLevel(
                            module_id=module.id,
                            question_id=question.id,
                            position=position,
                        )
                    )
                    counts["levels"] += 1

        database.commit()

    return counts


def seed_questions() -> tuple[int, int, int]:
    """Backward-compatible wrapper used by older docs/commands."""

    counts = seed_all()
    return counts["quizzes"], counts["questions"], counts["questions"]


if __name__ == "__main__":
    result = seed_all()
    print(
        "Seed complete: "
        f"{result['topics']} topics, {result['questions']} questions, "
        f"{result['quizzes']} quizzes, {result['quiz_links']} quiz links, "
        f"{result['modules']} modules, {result['levels']} levels."
    )
