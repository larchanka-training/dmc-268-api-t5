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

- [Архитектура](BACKEND_ARCHITECTURE.md)
- [Схема PostgreSQL и словарь 34 сущностей](docs/DATABASE_SCHEMA.md)
- [Очередь и восстановление](docs/QUEUE_RECOVERY.md)
- [Исходники ER-диаграмм Mermaid](docs/erd/README.md)

Документы версии 2.3 описывают проект, а не готовую реализацию.
Этот PR включает только документацию. SQLAlchemy-модели, миграции Alembic
и тесты остаются отдельной работой по
[задаче №6](https://github.com/larchanka-training/dmc-268-api-t6/issues/6).
