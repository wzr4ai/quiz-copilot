# Backend

## Local services with Docker Compose
The Postgres and Redis setup for local development lives in `backend/docker/docker-compose.dev.yml`.

1. Copy the sample env file: `cp backend/docker/.env.example backend/docker/.env`.
2. Start services: `docker compose -f backend/docker/docker-compose.dev.yml up -d`.
3. Stop services when done: `docker compose -f backend/docker/docker-compose.dev.yml down`.

## Development server

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e backend
python backend/main.py  # runs uvicorn app.main:app
```

The FastAPI app now lives under `backend/src/app/main.py` (src-layout) and currently exposes draft routers for auth, banks, questions, and study flows. Endpoints return mock data until database and AI services are wired up.
