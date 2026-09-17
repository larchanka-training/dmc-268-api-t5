# DMC-268 API (Team 5)

FastAPI backend с архитектурой Hexagonal и PostgreSQL-хранилищем.
Связанная задача: [dmc-268-api-t6#6](https://github.com/larchanka-training/dmc-268-api-t6/issues/6).
Целевой репозиторий этого изменения — **dmc-268-api-t5**.

Реализованы 34 SQLAlchemy 2.x модели, первая миграция Alembic, физические ERD,
явный Unit of Work и PostgreSQL-тесты. Работающие HTTP-маршруты пока только
`GET /` и `GET /health`. Ревью, GitHub/Ollama, авторизация, очередь и платёжные
сценарии описаны в архитектуре, но ещё не реализованы.

## Документация

- [Архитектура](BACKEND_ARCHITECTURE.md)
- [Словарь полей и ограничений](docs/DATABASE_SCHEMA.md)
- [Физическая ERD из моделей](docs/erd/README.md)
- [Протокол очереди и восстановления](docs/QUEUE_RECOVERY.md)
- [Реализованные гарантии, уточнения и оставшаяся работа](docs/IMPLEMENTATION_STATUS.md)

## Установка и запуск

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --locked
uv run uvicorn main:app --reload
```

Для совместимости поддерживается `pip install -r requirements.txt` в виртуальном
окружении. Воспроизводимая установка зависимостей — через `uv.lock`.
Приложение не подключается к БД при импорте и не запускает миграции автоматически.

## Миграции

Создайте отдельную PostgreSQL-базу и задайте `DATABASE_URL`, например:

```bash
export DATABASE_URL='postgresql+psycopg://code_review:code_review@localhost:5432/code_review'
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

`.env.example` содержит только примеры. Переменные нужно экспортировать в оболочку
или передать средствами запуска: автоматического чтения `.env` нет.
Приложение и миграции используют драйвер `postgresql+psycopg`; Unit of Work работает
через AsyncSession, Alembic — через синхронное соединение того же драйвера.

`uv run alembic upgrade head --sql` выводит SQL без подключения к БД.
Откат `uv run alembic downgrade base` **удаляет все 34 таблицы и их данные**;
используйте его только в одноразовой среде. Выпуск в существующую базу требует
обычного процесса миграции и резервного копирования команды.

Миграция содержит собственное описание DDL и не импортирует изменяемые модели.
Циклические FK принятой попытки/платежа добавляются после таблиц и снимаются до отката.

## Проверки

```bash
uv run ruff check .
uv run ruff format --check .
uv run pylint src/code_review main.py
export TEST_DATABASE_URL='postgresql+psycopg://code_review:code_review@localhost:5432/code_review_test'
uv run pytest -q
```

Тестам нужна отдельная одноразовая PostgreSQL-база и право `CREATE SCHEMA`.
Они создают случайную схему `test_<uuid>`, применяют настоящую миграцию и удаляют
только свою схему. Без `TEST_DATABASE_URL` проверки PostgreSQL явно пропускаются;
такой запуск не подтверждает исправность миграции. CI запускает полный набор на
PostgreSQL 18. SQLite не заменяет проверки JSONB, составных FK, частичных индексов
и блокировок PostgreSQL.

Проверяются upgrade/downgrade/upgrade, отсутствие Alembic drift, tenant и parent FK,
идемпотентность хранения, уникальность активных операций, конкуренция двух checkout,
`SKIP LOCKED` и явный commit/rollback. Эти тесты не заменяют будущие AU/QR-тесты
бизнес-сценариев из проектной документации.

Перегенерация диаграмм: `uv run python scripts/export_erd.py`.
