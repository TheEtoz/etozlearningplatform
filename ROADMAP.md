# ETOZ Platform — Development Roadmap

Step-by-step plan from MVP to production. Complete and verify each step before moving to the next.

**How to use this:** Say `"Ready for Step N"` when you want to begin a step. After implementation, run the verification checklist and confirm before proceeding.

---

## Progress Overview

| Step | Name | Status |
|------|------|--------|
| 1 | Project setup, Hello World | ✅ Done |
| 2 | Database models & configuration | ✅ Done |
| 3 | Authentication (register/login/logout) | ✅ Done |
| 4 | Pydantic schemas & API route structure | ✅ Done |
| 5 | Question library & seed data | ✅ Done |
| 6 | MCQ practice (backend + frontend) | ✅ Done |
| 7 | Python coding with Docker execution | ✅ Done |
| 8 | Progress tracking & dashboard | ✅ Done |
| 9 | Teacher/admin panel | ✅ Done |
| 10 | Testing, security & production deployment | ✅ Done |

---

## Step 1 — Project Setup ✅

**Goal:** Bootstrapped project with FastAPI + Streamlit Hello World.

**Deliverables:**
- Folder structure (Clean Architecture)
- Virtual environment, requirements.txt, .gitignore
- FastAPI and Streamlit entry points

**Verify:**
- [ ] `uvicorn backend.main:app --reload --port 8000` → JSON at http://localhost:8000
- [ ] `streamlit run frontend/app.py` → Welcome page at http://localhost:8501

---

## Step 2 — Database Models & Configuration ✅

**Goal:** PostgreSQL schema defined in code with Alembic migrations.

**Deliverables:**
- `config.py`, `database.py`
- Models: User, Question, Submission, Progress
- Alembic initial migration

**Verify:**
- [ ] `.env` created with valid `DATABASE_URL`
- [ ] `alembic upgrade head` succeeds
- [ ] Tables exist in PostgreSQL (pgAdmin or `\dt` in psql)
- [ ] `pytest` passes

---

## Step 3 — Authentication (Register / Login / Logout) ✅

**Goal:** Users can create accounts and log in securely. JWT tokens protect future API routes.

**Why:** Every feature (submissions, progress) needs to know *who* the user is.

**Deliverables:**
- `backend/security.py` — password hashing (bcrypt), JWT create/verify
- `backend/schemas/user.py` — UserCreate, UserLogin, UserResponse, Token
- `backend/routes/auth.py` — POST /register, POST /login, GET /me
- `backend/dependencies.py` — `get_current_user` dependency
- `frontend/pages/Login.py`, `Register.py`
- `frontend/utils/api.py`, `session.py` — API calls, token storage

**Verify:**
- [ ] Register new user via API (`/docs` or curl) → user in `users` table
- [ ] Login returns JWT access token
- [ ] `/me` with token returns user info; without token → 401
- [ ] Duplicate username/email → 400
- [ ] Streamlit Login/Register pages work and store token in session
- [ ] Passwords stored as hashes, never plain text

**Common mistakes:** Storing plain passwords; forgetting to hash; not validating token expiry.

---

## Step 4 — Pydantic Schemas & API Route Structure ✅

**Goal:** Clean API layer with validated request/response shapes and organized routes.

**Why:** Separates validation from business logic. Makes API docs accurate and catches bad input early.

**Deliverables:**
- `backend/schemas/question.py`, `submission.py`, `progress.py`
- `backend/routes/questions.py`, `submissions.py`, `progress.py` (stubs or read-only)
- Wire routers into `main.py` with prefixes (`/api/v1/auth`, `/api/v1/questions`, etc.)
- CORS middleware for Streamlit → FastAPI

**Verify:**
- [ ] All routes visible at http://localhost:8000/docs
- [ ] Invalid request body → 422 with clear validation errors
- [ ] CORS allows Streamlit origin (no browser block errors)
- [ ] Protected routes require `Authorization: Bearer <token>`

**Common mistakes:** Putting validation logic in routes instead of schemas; no API versioning.

---

## Step 5 — Question Library & Seed Data ✅

**Goal:** Questions exist in the database. Students can browse and filter them.

**Deliverables:**
- `database/seed.py` — sample MCQ and coding questions
- `backend/services/question_service.py` — list, filter, get by id
- `backend/routes/questions.py` — GET /questions (filters: topic, difficulty, type)
- `frontend/pages/Practice.py` — question list UI (read-only browse)

**Verify:**
- [ ] `python -m database.seed` (or equivalent) inserts sample questions
- [ ] GET /questions returns list with pagination/filters
- [ ] GET /questions/{id} returns single question (no correct_answer exposed to students)
- [ ] Streamlit Practice page shows categorized questions

**Common mistakes:** Exposing `correct_answer` in API responses; no seed script for dev.

---

## Step 6 — MCQ Practice (Backend + Frontend) ✅

**Goal:** Students answer MCQ questions and get instant feedback. Submissions and scores are saved.

**Deliverables:**
- `backend/services/submission_service.py` — submit MCQ answer, compute score
- POST /submissions (MCQ type)
- Update progress on correct/incorrect
- `frontend/pages/Practice.py` — select question, submit answer, show feedback

**Verify:**
- [ ] Submit correct answer → score 100, status `passed`
- [ ] Submit wrong answer → score 0, status `failed`
- [ ] Submission row in DB with user_id, question_id, answer
- [ ] Progress table updates (questions_attempted, questions_correct, accuracy)
- [ ] Streamlit shows instant feedback after submit

**Common mistakes:** Not linking submission to logged-in user; not updating progress.

---

## Step 7 — Python Coding with Docker Execution ✅

**Goal:** Students write Python code. Code runs safely in an isolated Docker container.

**Why:** Never execute student code on the host — security risk.

**Deliverables:**
- `docker/Dockerfile`, `docker/runner.py`
- `backend/services/docker_service.py` — create container, run code, collect stdout/stderr, destroy
- POST /submissions (coding type) — run tests, return pass/fail
- `frontend/pages/Coding.py` — code editor, Run button, output console

**Verify:**
- [ ] `print("hello")` → stdout in response
- [ ] Syntax error → stderr, status `error`
- [ ] Test cases pass/fail correctly
- [ ] Container has no network, CPU/memory/time limits
- [ ] Container destroyed after each run
- [ ] Streamlit Coding page runs code and shows output

**Common mistakes:** Running code directly on server; no timeout; leaving containers running.

---

## Step 8 — Progress Tracking & Dashboard ✅

**Goal:** Students see their learning stats — questions solved, accuracy, weak topics.

**Deliverables:**
- `backend/services/progress_service.py` — aggregate stats, weak topics
- GET /progress, GET /progress/summary
- `frontend/pages/Dashboard.py` — charts/stats, recent activity
- `frontend/pages/Profile.py` — user info, logout

**Verify:**
- [ ] Dashboard shows questions_attempted, accuracy per topic
- [ ] Weak topics identified (e.g. accuracy &lt; 70%)
- [ ] Recent submissions listed
- [ ] Profile page shows username, logout clears session

**Common mistakes:** Computing stats on every request instead of using Progress table.

---

## Step 9 — Teacher/Admin Panel ✅

**Goal:** Teachers can add, edit, and delete questions without touching the database directly.

**Deliverables:**
- Role field on User (student vs admin) or simple admin check
- POST/PUT/DELETE /questions (admin only)
- `frontend/pages/Admin.py` or admin section — CRUD form for questions

**Verify:**
- [ ] Non-admin cannot create/edit/delete questions → 403
- [ ] Admin can create MCQ and coding questions
- [ ] Admin can edit and delete questions
- [ ] New questions appear in Practice/Coding pages

**Common mistakes:** No authorization check; admin routes exposed to all users.

---

## Step 10 — Testing, Security & Production Deployment ✅

**Goal:** Production-ready app deployed and secure.

**Note:** Actual cloud deploy is operator-specific — see [`DEPLOYMENT.md`](DEPLOYMENT.md).

**Deliverables:**
- `tests/` — API tests (auth, questions, submissions)
- Security: rate limiting, input sanitization, secure headers
- `.env.example` updated for production
- Docker Compose for local full stack (optional)
- Deploy: Backend → Render, Frontend → Streamlit Cloud, DB → Neon PostgreSQL
- Health check, logging, error handling

**Verify:**
- [ ] `pytest` passes all tests
- [ ] Backend deployed and reachable
- [ ] Frontend deployed and connects to backend
- [ ] Database on Neon, migrations applied
- [ ] Login/register works in production
- [ ] No secrets in Git; env vars set in hosting dashboards

**Common mistakes:** Deploying with DEBUG=True; hardcoded URLs; no HTTPS.

---

## After Production (Future Enhancements)

- Java, C++, JavaScript support
- AI Tutor integration
- Courses and assignments
- Teacher dashboard (class management)
- Email verification, password reset

---

## Quick Reference — Commands

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Backend
uvicorn backend.main:app --reload --port 8000

# Frontend
streamlit run frontend/app.py

# Database
alembic upgrade head
alembic current

# Tests
pytest -v
```

---

*Last updated: UX redesign — question bank, mixed quizzes, coding path, role hubs. See DEPLOYMENT.md for hosting.*
