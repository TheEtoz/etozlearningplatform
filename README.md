# ETOZ Learning Platform (MVP)

An online programming learning platform where beginners can learn Python through MCQ questions and coding exercises.

## Tech Stack

| Layer      | Technology        |
|------------|-------------------|
| Frontend   | Streamlit         |
| Backend    | FastAPI           |
| Database   | PostgreSQL        |
| ORM        | SQLAlchemy        |
| Auth       | JWT + bcrypt      |
| Migrations | Alembic           |
| Code Run   | Docker            |

## Project Structure

```
etoz-platform/
├── frontend/          # Streamlit UI (what students see)
│   ├── app.py         # Main entry point
│   ├── pages/         # Individual pages (Login, Practice, etc.)
│   └── utils/         # Frontend helpers (API calls, session)
├── backend/           # FastAPI API (business logic + data)
│   ├── main.py        # Server entry point
│   ├── models/        # Database table definitions
│   ├── schemas/       # Request/response validation
│   ├── routes/        # API endpoints
│   └── services/      # Business logic
├── database/          # SQL schema and seed data
├── docker/            # Safe Python code execution
└── tests/             # Automated tests
```

## Getting Started (Step 1)

### Prerequisites

- Python 3.11 or newer
- Git
- PostgreSQL 15 or newer

### 1. Clone and enter the project

```bash
cd etoz-platform
```

### 2. Create and activate virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env` and change `SECRET_KEY` to a random string.

### 5. Run the backend

**Recommended:**

```powershell
python run_backend.py
```

Or manually:

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — you should see the Hello World JSON message.

Interactive API docs: http://127.0.0.1:8000/docs

Database health check: http://127.0.0.1:8000/health/db

If login/register time out, stop old backend processes still using port 8000,
then start the backend again with `python run_backend.py`.

### 6. Run the frontend (in a second terminal)

**Recommended:**

```powershell
python run_frontend.py
```

Or manually:

```powershell
streamlit run frontend/app.py
```

Both commands must be run from the project root (`D:\projects\etoz-platform`).
The frontend uses `from frontend.utils...` imports, so Python needs the project
root on its import path. `run_frontend.py` handles that automatically.

Open http://localhost:8501 — you should see the welcome page.

## Database Setup (Step 2)

SQLAlchemy models describe the database in Python. Alembic migrations apply
those model changes to PostgreSQL in a repeatable, version-controlled way.

### 1. Create a local PostgreSQL database

Use pgAdmin or PostgreSQL's command-line tools to create a database named
`etoz_db`. Create a dedicated database user instead of using the PostgreSQL
administrator account in an application.

### 2. Configure the connection

Create `.env` from `.env.example`, then replace the placeholders:

```dotenv
DATABASE_URL=postgresql+psycopg2://your_user:your_password@localhost:5432/etoz_db
```

The `.env` file is ignored by Git because it contains credentials.

### 3. Apply migrations

```powershell
.\venv\Scripts\Activate.ps1
alembic upgrade head
```

Useful Alembic commands:

```powershell
alembic current           # Show the database's current revision
alembic history           # Show all available revisions
alembic downgrade -1      # Undo the latest revision
```

Do not call `Base.metadata.create_all()` in the application. It bypasses
Alembic's migration history and makes production schema changes difficult to
review and reproduce.

## Seed Beginner Questions (Step 5+)

Load starter MCQs and coding exercises with:

```powershell
python -m database.seed
```

The command is idempotent: running it again skips quizzes/questions that already
exist. It also seeds a demo teacher (`demo_teacher` / `password123`) and two
demo classes — one public (`PUBLIC01`) and one private (`PRIVATE1`).

Students enroll via **Classes**, then open a class to take published quizzes and
the class learning path. Teachers manage classes under **Classes** (publish
quizzes/modules, roster, performance). Content is **class-scoped** for students:
they only see what is published to classes they join.

Teachers can keep quizzes/questions **private** or **shared** (Global Question /
Quiz Bank). Importing a quiz into a class **copies** it by default. Modules are
ordered **blocks** (lecture, text, MCQ, coding) edited on a dedicated module
editor page.

Some quizzes are **timed by design** (teacher setting); others are untimed.
Correct answers are revealed only after you finish a quiz.

## Docker Code Sandbox (Step 7)

Student code never runs on the host. Install **Docker Desktop**, start it, then
build the runner image from the project root:

```powershell
docker build -t etoz-python-runner -f docker/Dockerfile docker
```

Verify:

```powershell
docker version
```

Details: [`docker/README.md`](docker/README.md)

## Development Roadmap

Full step-by-step plan with verification checklists: **[ROADMAP.md](ROADMAP.md)**

| Step | Status | Description |
|------|--------|-------------|
| 1 | ✅ | Project setup, Hello World |
| 2 | ✅ | Database models & configuration |
| 3 | ✅ | Authentication (register/login/logout) |
| 4 | ✅ | Pydantic schemas & API route structure |
| 5 | ✅ | Question library & seed data |
| 6 | ✅ | MCQ practice (backend + frontend) |
| 7 | ✅ | Python coding with Docker execution |
| 8 | ✅ | Progress tracking & dashboard |
| 9 | ✅ | Teacher/admin panel |
| 10 | ✅ | Testing, security & production deployment |

Deployment guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

Promote a teacher: `python -m database.promote_admin <username>`

## License

Private — ETOZ Learning Platform MVP
