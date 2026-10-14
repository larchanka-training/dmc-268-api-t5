# DMC-268 API (Team 5)

FastAPI backend service for DMC-268 Team 5.

## Quick start (Docker)

```bash
docker compose up --build
curl http://localhost:8000/healthcheck   # {"status":"ok"}
```

Compose starts the API, PostgreSQL 17 and Redis 7. Optional overrides
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) go into a local `.env`.

## Local development (Poetry, Python 3.13)

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
pull request and before each deploy (push to `main`, `develop` or `feature/**`).

## Branch naming

Branches must be named `<type>/<short-name>` (lowercase latin letters, digits, `-` or `_`), where `<type>` is one of
`feat` (or its alias `feature`), `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `hotfix`
(e.g. `feat/add-healthcheck`, `fix/12-db-timeout`). The name is checked in
GitHub Actions (`.github/workflows/branch-name.yml`) on every pull request and
before each deploy.

## Deploy

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Caddy (set up by Terraform) serves
`https://<domain>/api/*` (production) and `https://staging.<domain>/api/*`
(staging); without `APP_DOMAIN` the domain is `<ip-with-dashes>.sslip.io`.
A push to `main` deploys to
production, a push to `develop` or `feature/**` deploys to staging (after CI and the branch
name check). API, worker and Postgres run as Docker Swarm services; secrets are
mounted as files in `/run/secrets`. A failed health check after deploy rolls back to the previous
version automatically.
