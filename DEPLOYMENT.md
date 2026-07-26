# Deployment Guide (Step 10)

ETOZ MVP deployment checklist. **Do not commit secrets** — set them in each host’s dashboard.

## Recommended architecture

| Piece | Host | Notes |
|--------|------|--------|
| PostgreSQL | [Neon](https://neon.tech) | Managed Postgres; use SSL connection string |
| FastAPI API | VPS with Docker (DigitalOcean, Hetzner, etc.) | Needed if coding sandbox is enabled |
| Streamlit UI | [Streamlit Community Cloud](https://streamlit.io/cloud) | Set `BACKEND_URL` to your HTTPS API |
| Code sandbox | Same VPS as the API | Docker engine + `etoz-python-runner` image |

> **Why not Render free tier for coding?** Many PaaS web services cannot start sibling containers. Auth/MCQ/progress can live on a PaaS; **Run/Submit code needs a host with Docker**.

## 1. Database (Neon)

1. Create a Neon project and copy the connection string.
2. Set `DATABASE_URL` to the SQLAlchemy form:
   `postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require`
3. From your machine (or CI):
   ```bash
   alembic upgrade head
   python -m database.seed
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
   ADMIN_USERNAMES=["teacher"]
   DOCKER_IMAGE=etoz-python-runner
   ```
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

- Register a username listed in `ADMIN_USERNAMES`, **or**
- `python -m database.promote_admin <username>`

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
