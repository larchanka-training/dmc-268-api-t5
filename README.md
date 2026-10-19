# DMC-268 API (Team 5)

FastAPI backend service for DMC-268 Team 5.

## Quick start (Docker)

```bash
docker compose up --build
curl http://localhost:8000/healthcheck   # {"status":"ok"}
```

Compose starts the API, PostgreSQL 17 and Redis 7. Optional overrides
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) go into a local `.env`.

## Architecture and database

- [docs/BACKEND_ARCHITECTURE.md](docs/BACKEND_ARCHITECTURE.md) — backend architecture (Router → Service → Repository → LLM Gateway), ER model, ORM and migrations.
- [docs/diagrams/erd.mmd](docs/diagrams/erd.mmd) — ER diagram (Mermaid).
- Models: `app/infrastructure/db/models/`. Migrations: `alembic/versions/`.

```bash
docker compose up -d --wait db
poetry run alembic upgrade head
poetry run alembic check   # models match the schema
```

## Local development (Poetry, Python 3.14)

```bash
poetry install
poetry run pre-commit install
poetry run uvicorn app.main:app --reload
```

## Checks

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
poetry run pytest
```

The same checks run in GitHub Actions (`.github/workflows/ci.yml`) on every
push to `main` and every pull request, and before each release.

## Deploy

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Releases are triggered by a
`v*.*.*` tag; a failed health check after deploy rolls back to the previous
container automatically.
