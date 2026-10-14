# Инструкция по релизу и деплою: dmc-268-api-t5

Документ описывает цикл сборки, доставки и безопасного управления секретами для сервиса API на целевом сервере Hetzner.

---

## 1. Архитектура и безопасность секретов

- **Docker Swarm secrets.** API, worker и Postgres работают как swarm-сервисы на одном узле. Swarm инициализируется Terraform и деплоем: `docker swarm init --advertise-addr 127.0.0.1`, управляющие порты слушают только localhost.
- Swarm и `dmc-overlay` создает Terraform; деплой повторяет это идемпотентно на случай, если Terraform еще не перезапускали.
- Секреты (`DB_PASSWORD`, `AI_DMC268_T5`) GitHub Actions передает в ssh-сессию через `envs:` ssh-action, в текст скрипта они не подставляются. Деплой создает из них swarm secrets: `printf '%s' "$X" | docker secret create <имя> -`.
- Swarm хранит секреты в зашифрованном raft-логе. В контейнер они монтируются файлами в tmpfs `/run/secrets/<имя>` (владелец `appuser`, режим `0400`). В переменных окружения контейнера, в `docker inspect` и в `config.v2.json` секретов нет.
- Приложение читает их через `secrets_dir` в pydantic-settings (`app/core/config.py`): файл `/run/secrets/database_url` попадает в поле `database_url`, `/run/secrets/llm_api_key` в `llm_api_key`. Переменные окружения имеют приоритет (так работает `docker-compose.yml` локально).
- Postgres получает пароль суперпользователя `postgres` через `POSTGRES_PASSWORD_FILE` только при первой инициализации `dmc-pgdata`. Приложение под `postgres` не подключается, деплой работает с ним через локальный сокет внутри контейнера.
- **Отдельная роль на окружение.** Роль `dmc_prod` / `dmc_staging` владеет своей БД, без прав superuser, createdb и createrole. Право `CONNECT` у `PUBLIC` отозвано, поэтому staging не может подключиться к БД prod. Пароль роли — `DB_PASSWORD` окружения, деплой обновляет его при каждом запуске (`ALTER ROLE`), так что смена секрета применяется сама. Чтобы пароли prod и staging различались, задайте `DB_PASSWORD` отдельно в **Settings -> Environments** для `production` и `staging`.
- Секреты в swarm неизменяемы. Каждый деплой создает новые (`dmc-database-url-<env>-<run_id>`), подменяет их в сервисе и после успешной проверки удаляет неиспользуемые.
- Учетные данные GHCR удаляются с VPS (`docker logout`) сразу после `docker pull`.
- **Сетевая изоляция**: сервисы работают в overlay-сети `dmc-overlay` (attachable). `dmc-redis` (standalone-контейнер из Terraform) подключается к ней деплоем.

---

## 2. Необходимые секреты в GitHub Actions

В разделе **Settings -> Secrets and variables -> Actions** репозитория:

| Название секрета | Назначение |
| :--- | :--- |
| `VPS_DMC268_IP_T5` (Variable, не Secret) | IP-адрес сервера Hetzner |
| `VPS_DMC268_U` | SSH-пользователь |
| `VPS_DMC268_P` | Пароль пользователя SSH |
| `AI_DMC268_T5` | Токен/ключ для работы с LLM |
| `DB_PASSWORD` | Пароль подключения к БД |

Необязательная переменная (**Variable**, не Secret):

| Название переменной | Назначение |
| :--- | :--- |
| `APP_DOMAIN` | Домен production, staging живет на `staging.<домен>`. A-записи обоих имен должны указывать на IP VPS. Если не задана, используется `<ip-через-дефисы>.sslip.io` (например `1-2-3-4.sslip.io`), DNS настраивать не нужно. |

Одна и та же переменная используется Terraform (`TF_VAR_app_domain`), деплоем API и деплоем UI.

---

## 3. Подготовка VPS (Terraform)

Workflow `.github/workflows/terraform-bootstrap.yml` запускается вручную (**Actions** -> **Terraform Deploy to VPS** -> **Run workflow**) и при изменении `terraform/**` в `main`. Он готовит VPS:

- **Firewall (ufw)**: входящие разрешены только на SSH (порт берется из `sshd -T`, плюс 22), 80 и 443 (tcp и udp). Остальное запрещено. Порты, опубликованные через `docker -p`, обходят ufw, поэтому наружу их публикует только `dmc-caddy`. Если порты публикует какой-то другой контейнер, Terraform выведет предупреждение;
- Docker, сеть `dmc-net`, Swarm (один узел) и overlay-сеть `dmc-overlay`;
- Redis `dmc-redis` и volume `dmc-pgdata` для Postgres;
- **Бэкап Postgres**: cron `/etc/cron.d/dmc-pg-backup` каждый день в 03:30 запускает `/usr/local/bin/dmc-pg-backup` (исходник `terraform/pg-backup.sh`). В `/var/backups/dmc-postgres` (доступ только root) сохраняются `pg_dump -Fc` каждой БД `dmc_*` и `pg_dumpall --globals-only` (роли). Срок хранения 14 дней, лог в `/var/log/dmc-pg-backup.log`. Бэкапы лежат на том же VPS и не спасут при потере сервера: для этого их нужно копировать во внешнее хранилище;
- **Caddy** `dmc-caddy`: единственная точка входа, порты 80/443. TLS-сертификаты Let's Encrypt Caddy получает и продлевает сам, они хранятся в volume `dmc-caddydata`. Конфигурация: `terraform/Caddyfile.tftpl`, на сервере `/opt/dmc-268/caddy/Caddyfile`.

Terraform нужно запустить **до первого деплоя** API и UI и после каждой смены `APP_DOMAIN`. Без Caddy деплой пройдет, но проверка с раннера по HTTPS упадет и вызовет откат.

| Адрес | Куда |
| :--- | :--- |
| `https://<домен>/` | `dmc-ui-prod` |
| `https://<домен>/api/*` | `dmc-api-prod:8000`, префикс `/api` снимается |
| `https://staging.<домен>/` | `dmc-ui-staging` |
| `https://staging.<домен>/api/*` | `dmc-api-staging:8000`, префикс `/api` снимается |

Например, `https://<домен>/api/healthcheck` попадает в `/healthcheck` API. UI и API живут на одном origin, поэтому CORS не нужен. Порты API и UI наружу не публикуются.

Let's Encrypt ограничивает число сертификатов на зарегистрированный домен в неделю. Для sslip.io лимит общий со всеми его пользователями. Если выпуск упрется в лимит, задайте свой домен в `APP_DOMAIN`.

---

## 4. Окружения и автодеплой

Один VPS, два окружения. Деплой запускается автоматически при пуше (после прохождения CI):

| Ветка | Environment | Swarm-сервисы | Адрес API | БД Postgres | Redis DB |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `main` | `production` | `dmc-api-prod`, `dmc-worker-prod` | `https://<домен>/api/` | `dmc_prod` | 0 |
| `develop` | `staging` | `dmc-api-staging`, `dmc-worker-staging` | `https://staging.<домен>/api/` | `dmc_staging` | 1 |

Пуш в feature-ветки не деплоит. Любую ветку можно задеплоить вручную: **Actions -> API Release Pipeline -> Run workflow**, выбрать ветку и окружение (`staging` или `production`). Деплой перезаписывает текущую версию окружения. Чтобы в production нельзя было выкатить произвольную ветку, ограничьте ее в **Settings -> Environments -> production** (Deployment branches и/или Required reviewers).

- Общие `dmc-postgres` (swarm-сервис, создается деплоем, volume `dmc-pgdata`) и `dmc-redis` (контейнер из Terraform). Порты наружу не публикуются, доступны только в сети `dmc-overlay`.
- Первый деплой после перехода на swarm удаляет старые standalone-контейнеры `dmc-postgres`, `dmc-api-*`, `dmc-worker-*` и создает сервисы. Данные Postgres сохраняются в volume. API недоступен несколько секунд.
- Worker (ARQ) запускается из того же образа командой `arq app.worker.WorkerSettings`.
- Тег образа: SHA коммита. Обновление rolling (`--update-order start-first`): новая задача поднимается рядом со старой, старая останавливается, когда новая стала healthy.
- Откат: если новая версия не стала healthy, swarm откатывает сервис сам (`--update-failure-action rollback`). При падении `/healthcheck` после обновления, падении worker (`arq --check`) или проверки с раннера деплой вызывает `docker service rollback`.
- Пароль БД в `DATABASE_URL` кодируется (percent-encoding), спецсимволы допустимы.
- Секреты можно задать отдельно на каждый Environment (**Settings -> Environments**), иначе используются репозиторные.

---

## 5. Восстановление Postgres из бэкапа

```bash
# на VPS под root
dmc-pg-backup                                   # внеплановый бэкап
ls -lt /var/backups/dmc-postgres | head         # выбрать файл
CID=$(docker ps -q --filter label=com.docker.swarm.service.name=dmc-postgres | head -n 1)
docker service scale dmc-api-prod=0 dmc-worker-prod=0   # остановить приложение окружения
docker exec -i "$CID" pg_restore -U postgres -d dmc_prod --clean --if-exists --no-owner --role=dmc_prod \
  < /var/backups/dmc-postgres/dmc_prod-YYYYMMDD-HHMMSS.dump
docker service scale dmc-api-prod=1 dmc-worker-prod=1
```

Для staging замените `prod` на `staging`. Роли восстанавливаются из `globals-*.sql`: `docker exec -i "$CID" psql -U postgres < globals-....sql`.
