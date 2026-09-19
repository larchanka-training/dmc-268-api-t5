# DMC-268 API (Team 5)

FastAPI backend service for DMC-268 Team 5.

## Setup & Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Документация backend

- [Архитектура backend по arc42](ARCHITECTURE.md)
- [ER-диаграмма PostgreSQL](docs/diagrams/erd.mmd)
- [Пример Nginx / API Gateway](deploy/nginx.conf)

Архитектура описывает RabbitMQ → bridge → BullMQ/Redis → workers,
правила ревью, авторизацию, токенный бюджет, развёртывание и сценарии сбоев.
Структура проекта и команды Compose/Kubernetes в документе — план реализации.
SQLAlchemy-модели, миграции Alembic и исполняемые тесты добавляются отдельно
в рамках [задачи №5](https://github.com/larchanka-training/dmc-268-api-t5/issues/5).
