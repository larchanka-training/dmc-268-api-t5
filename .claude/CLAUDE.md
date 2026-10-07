# DMC-268 API (Team 5)

FastAPI-бэкенд для DMC-268 Team 5. Деплой на VPS Hetzner через GitHub Actions и Terraform.

## Стек и структура

- Python 3.13, FastAPI, uvicorn, Poetry (`pyproject.toml`, `poetry.lock`); код в `app/` (`api/`, `core/`), тесты в `tests/`.
- Линтеры: ruff, mypy strict, pre-commit. `Dockerfile` и `docker-compose.yml` в корне.
- `terraform/` — bootstrap VPS (docker, сеть `dmc-net`, базовый nginx).
- `.github/workflows/` — `ci.yml` (ruff, mypy, pytest, compose smoke), `release-deploy.yml` (ci → build → push в GHCR → деплой по тегу `v*.*.*` с healthcheck и откатом), `terraform-bootstrap.yml`.
- `docs/DEPLOYMENT.md` — схема релиза и секретов.
- Деплой: контейнер `dmc-api`, сеть `dmc-net`, порт 8000, секреты передаются через stdin (`--env-file -`), на диск VPS не пишутся.

## Команды

- Установка: `poetry install` (Python 3.13); хуки: `poetry run pre-commit install`
- Запуск локально: `poetry run uvicorn app.main:app --reload`
- Запуск стека: `docker compose up --build` (api + postgres + redis), `GET /healthcheck` → 200
- Проверки: `poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy .`, `poetry run pytest`
- Те же проверки в CI: `.github/workflows/ci.yml`.
- В песочнице Claude pip не может скачать пакеты (SSL), поэтому Poetry-команды запускает пользователь.

## Правила работы

- Отвечай на русском. Ответы краткие, без лишних пояснений.
- Перед выполнением команды в одной фразе объясни, что она делает и зачем.
- Сначала план, потом код: для нетривиальных задач опиши план и дождись согласия.
- Перед `git commit` и `git push` спрашивай подтверждение.
- Сообщения коммитов на русском, в стиле существующей истории репозитория.
- Код, имена переменных и комментарии на английском.
- Не читай и не изменяй `.env`, ключи и другие секреты. Не выводи их значения в ответах.
- Перед завершением задачи запусти тесты и линтер проекта и сообщи результат честно, включая падения.
- Перед любой задачей сначала прочитай `README.md`, `docs/`, `.github/workflows/` и `terraform/`, кратко перескажи ограничения и только потом предлагай план.
- Не обращайся к сети (pip, npm, curl и т.п.) и не ставь пакеты без явного разрешения.
