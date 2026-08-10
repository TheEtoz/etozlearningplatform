# Deployment Guide (Step 10)

ETOZ MVP deployment checklist. **Do not commit secrets** — set them in each host’s dashboard.

## Free stack ($0 — lectures / quizzes / auth; no Docker code run)

| Piece | Host | Notes |
|--------|------|--------|
| Code | GitHub | This repo |
| PostgreSQL | [Neon](https://neon.tech) free | Paste connection string into Render |
| FastAPI API | [Render](https://render.com) free Web Service | Uses root [`render.yaml`](render.yaml) Blueprint |
| Streamlit UI | [Streamlit Community Cloud](https://streamlit.io/cloud) | Main file `frontend/app.py` |

### Free deploy steps

1. **Neon** — create a project → copy the connection string (`postgres://…` or `postgresql://…` is fine; the API normalizes it for psycopg2). Optionally from your machine:
   ```powershell
   $env:DATABASE_URL = "postgresql://…?sslmode=require"
   python scripts/migrate_neon.py
   $env:ETOZ_SEED_DEMO = "1"
   python scripts/seed_demo_remote.py
   ```
   Migrations also run automatically on Render boot (`alembic upgrade head` in the start command; free tier has no `preDeployCommand`).

2. **Render** — Dashboard → New → Blueprint → select this repo (`render.yaml`).
   When prompted, set:
   - `DATABASE_URL` = Neon URI
   - `PUBLIC_API_URL` = `https://etoz-api.onrender.com` (match the service URL after create)
   - `FRONTEND_PUBLIC_URL` = your Streamlit URL (placeholder first if needed)
   - `CORS_ORIGINS` = `["https://YOUR-APP.streamlit.app"]`
   Confirm `GET /health` and `GET /health/db`.

3. **Streamlit Cloud** — New app from this repo, main file `frontend/app.py`.
   Secrets (see [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)):
   ```toml
   BACKEND_URL = "https://etoz-api.onrender.com"
   PUBLIC_MODE = "true"
   ```
   Then update Render `CORS_ORIGINS` / `FRONTEND_PUBLIC_URL` to the real Streamlit URL and redeploy.

4. **Teacher bootstrap** — register username `teacher` (listed in `ADMIN_USERNAMES`):
   ```powershell
   python scripts/bootstrap_teacher.py https://etoz-api.onrender.com teacher you@example.com 'YourPassword123'
   ```
   Or use the Register page in the Streamlit app.

> **Trade-off:** free Render cannot run the Docker coding sandbox. Lectures, MCQ, quizzes, login/register, and teacher editing work; Run/Submit code needs a Docker host (section below).

## Paid / Docker architecture (code execution)

| Piece | Host | Notes |
|--------|------|--------|
| PostgreSQL | [Neon](https://neon.tech) | Managed Postgres; use SSL connection string |
| FastAPI API | VPS with Docker (DigitalOcean, Hetzner, etc.) | Needed if coding sandbox is enabled |
| Streamlit UI | [Streamlit Community Cloud](https://streamlit.io/cloud) | Set `BACKEND_URL` to your HTTPS API |
| Code sandbox | Same VPS as the API | Docker engine + `etoz-python-runner` image |

> **Why not Render free tier for coding?** Many PaaS web services cannot start sibling containers. Auth/MCQ/progress can live on a PaaS; **Run/Submit code needs a host with Docker**.

## 1. Database (Neon)

1. Create a Neon project and copy the connection string.
2. Set `DATABASE_URL` — raw Neon URIs work; SQLAlchemy form is also fine:
   `postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require`
3. From your machine (or CI):
   ```bash
   python scripts/migrate_neon.py
   python scripts/seed_demo_remote.py
   ```

## 2. Backend (VPS with Docker)

1. Install Docker and Python 3.11+.
2. Clone the repo, create `.env` from `.env.example`.
3. Production `.env` essentials:
   ```dotenv
   DEBUG=False
   SECRET_KEY=<long-random-string>
   DATABASE_URL=postgresql+psycopg2://...
   CORS_ORIGINS=["https://YOUR_STREAMLIT_APP.streamlit.app"]
   FRONTEND_PUBLIC_URL=https://YOUR_STREAMLIT_APP.streamlit.app
   EMAIL_FROM=ETOZ <noreply@yourdomain.com>
   RESEND_API_KEY=re_xxxxxxxx
   # Or SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD instead of Resend
   ADMIN_USERNAMES=["teacher"]
   DOCKER_IMAGE=etoz-python-runner
   ```
   New users must verify email before login. Password reset uses the same mailer.
   Email links open Streamlit pages `VerifyEmail` and `ResetPassword` with `?token=...`.
4. Build the sandbox image:
   ```bash
   docker build -t etoz-python-runner -f docker/Dockerfile docker
   ```
5. Run the API (example):
   ```bash
   pip install -r requirements.txt
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
6. Put HTTPS in front (Caddy/Nginx) and point Streamlit at that URL.

## 3. Frontend (Streamlit Cloud)

1. Deploy `frontend/app.py` from this repo.
2. Set secrets / env:
   - `BACKEND_URL=https://api.your-domain.com`
3. Confirm CORS on the API allows the Streamlit origin.

## 4. Admin bootstrap

- Register a username listed in `ADMIN_USERNAMES`, verify the email, **or**
- `python -m database.promote_admin <username>` (existing verified accounts)
- Local/demo seed creates verified `demo_teacher` / `password123` with demo classes.
  **Never run `python -m database.seed` against production.** It refuses when
  `ETOZ_ENV=production` unless `ETOZ_SEED_DEMO=1` is set on a dedicated demo host.

## 4b. Classes (school workflow)

1. Teacher creates a class (public or private) and copies the enrollment code.
2. Publish quizzes/modules from the bank into the class.
3. Students enroll (browse public, or enter code) then open the class for quizzes/path.
4. Teacher reviews roster + performance on the class page.

## 5. Verify

- [ ] `GET /health` and `GET /health/db` return ok
- [ ] Register / login works
- [ ] Practice + Dashboard load
- [ ] Coding Run works only if Docker is available on the API host
- [ ] Non-admin gets 403 on `POST /api/v1/questions`
- [ ] `DEBUG=False` and default `SECRET_KEY` is rejected at startup

## Local Postgres via Compose

```powershell
docker compose up -d db
```

Then point `DATABASE_URL` at `postgresql+psycopg2://etoz:etoz@127.0.0.1:5432/etoz_db`.
