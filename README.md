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

```bash
uvicorn backend.main:app --reload --port 8000
```

Open http://localhost:8000 — you should see the Hello World JSON message.

Interactive API docs: http://localhost:8000/docs

### 6. Run the frontend (in a second terminal)

```bash
streamlit run frontend/app.py
```

Open http://localhost:8501 — you should see the welcome page.

## Development Roadmap

- [x] **Step 1** — Project setup, Hello World
- [ ] **Step 2** — Database models & configuration
- [ ] **Step 3** — Authentication (register/login)
- [ ] **Step 4** — Question library
- [ ] **Step 5** — MCQ practice
- [ ] **Step 6** — Python coding with Docker
- [ ] **Step 7** — Progress dashboard
- [ ] **Step 8** — Teacher/admin panel

## License

Private — ETOZ Learning Platform MVP
