"""Import all models so SQLAlchemy and Alembic discover every table."""

from backend.models.coding_module import CodingModule, ModuleLevel
from backend.models.progress import Progress
from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_attempt import QuizAttempt
from backend.models.quiz_question import QuizQuestion
from backend.models.submission import Submission
from backend.models.topic import Topic, question_topics
from backend.models.user import User

__all__ = [
    "CodingModule",
    "ModuleLevel",
    "Progress",
    "Question",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "Submission",
    "Topic",
    "User",
    "question_topics",
]
