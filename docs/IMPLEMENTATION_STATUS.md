# Статус реализации задачи №6

Версия комплекта **2.4**, 17 сентября 2026 года. Основа — три предоставленных
документа v2.3. Их проектные решения и открытые вопросы сохранены. Реализация
DoD касается архитектуры, структуры хранения и миграции; она не превращает
проектные бизнес-сценарии в работающий продукт.

## Что реализовано

| Артефакт | Реализация |
|---|---|
| Архитектура | Domain/application/adapters, composition root; ядро не импортирует FastAPI/SQLAlchemy |
| API | Совместимые `/` и `/health`, без подключения к БД при импорте |
| ORM | SQLAlchemy 2.x, 34 таблицы DB-01–DB-34, явные `Mapped` поля |
| Типы | UUID, TEXT, BIGINT/INTEGER, BOOLEAN, JSONB, TIMESTAMPTZ |
| Миграции | Alembic `0001`, upgrade/downgrade, offline SQL, проверка drift |
| Транзакции | AsyncSession factory, явный commit; rollback/close при выходе из Unit of Work |
| ERD | Все физические поля и составные FK, генерация из metadata |
| Воспроизводимость | uv.lock, Ruff/Pylint, CI с PostgreSQL 18 |

Модели не являются domain-объектами: они находятся в outbound PostgreSQL adapter.
Связи заданы через FK; ORM `relationship` и каскадные удаления не добавлены без
сценариев загрузки и утверждённой политики хранения. Удаления родителей блокируются
ссылками PostgreSQL. UUID создаются Python ORM; для raw SQL клиент обязан передать ID.
`created_at` и `received_at` имеют серверный `now()`.

## Гарантии хранения и проверки

| Область | Что проверяет БД / тест |
|---|---|
| Tenant | Составные FK исключают чужие integration, membership и остальные tenant-ссылки |
| Родители | Job принадлежит PR своего Request; prompt — перспективе; call — job перспективы; Finding и Comment — тому же job |
| Принятие | `ModelCall.accepted_attempt_id` относится к этому call; Finding ссылается на выбранную попытку через составной FK к ModelCall |
| Публикация | Уникальный publication_key в job; отдельные состояния неизвестного исхода |
| Очередь | Ровно одна цель по kind, конечный max_attempts, неотрицательные счётчики, running требует lease; индексы доступности/lease |
| Идемпотентность | Частичные UNIQUE по инициатору Request; ключи работ, входящих webhook, провайдерных операций |
| Активность | Один default profile, один queued/running job на Request, один незавершённый Payment на Purchase |
| Деньги и квота | Принятый Payment своего Purchase; account совпадает у Subscription/Purchase/Entitlement/BillingEntry; одно право по Purchase |
| Резерв | Счётчики не превышают total; одна финальная запись consume/release на резерв; settled_at согласован с состоянием |
| Конкуренция | Два параллельных checkout дают одну запись и один UNIQUE-конфликт; два SELECT SKIP LOCKED получают разные работы |
| Миграция | Настоящий upgrade/downgrade/upgrade, Alembic check, имена CHECK, соответствие словарю и ERD |

Частичный UNIQUE Payment включает `payment_unknown`. Два подтверждённых платежа
одного заказа сохраняются как отдельные факты. UNIQUE Entitlement предотвращает
повторное право по одному Purchase. Это локальные ограничения, а не гарантии
идемпотентности внешнего провайдера.

## Детализация словаря для физической схемы

Таблицы, поля, nullable и допустимые состояния v2.3 сохранены. Следующие детали
явно зафиксированы вместе с моделями и миграцией:

- Имена таблиц — `snake_case`; имена Python-классов соответствуют DB-01–DB-34.
- На tenant-таблицах с `id` есть UNIQUE(tenant_id, id). Дополнительные составные
  UNIQUE нужны как цели FK с job, PR, perspective, account и accepted attempt.
- `phase`, `category`, `severity`, формы JSONB, provider и currency остаются TEXT/
  JSONB без выдуманных enum, размеров и продуктовых значений.
- Положительны version, attempt_no, sequence_no, max_attempts, units и номер PR.
  Position, epochs, счётчики, суммы и токены неотрицательны. Численные верхние
  лимиты остаются OPEN-03. Примеры в тестах не задают производственную политику.
- `refresh_applied_seq <= refresh_requested_seq`; конец подписки позже начала.
- Для UsageReservation состояние `reserved` требует NULL settled_at, а consumed/
  released — заполненное время. Переход между финальными состояниями этим не защищён.
- BillingEntry для reserve/consume/release требует reservation_id. UNIQUE по
  reservation для consume/release защищает единственную запись финального решения.
- У Finding запрещена ссылка на себя; FK к ModelCall связывает attempt_id с
  accepted_attempt_id. Циклы между разными дубликатами требуют прикладной проверки.
- REC-06 упоминает hash окончательного тела Comment, которого нет отдельной колонкой
  в DB-25. В текущей схеме hash можно вычислять из сохранённого body; новый столбец
  не добавлен. Способ сверки должен быть уточнён при реализации публикации.

## Что остаётся проектом

OPEN-01–OPEN-08 остаются открытыми. Не реализованы авторизация и матрица ролей,
последний owner, приём приглашения, проверка GitHub App, webhook signature,
получение/продление lease, admission по token/epoch/deadline, фиксация ревизии,
бюджеты LLM, неизменяемость snapshot/payload/index, платежный checkout и выдача
прав, атомарный reserve/consume/release, unknown recovery и публикация комментариев.

InferenceAttempt связывается с WorkItem и ModelCall по tenant; проверка того,
что это именно run_review работа **того же job**, остаётся прикладной: в словаре
нет дополнительного job_id у attempt. FK не объявляется достаточным доказательством.
Аналогично семантика JSONB, точный commit RepositoryIndex, роль приглашения,
права инициатора, сохранение provider и защита от изменения принятого результата
требуют сценариев и конкурентных тестов.

AU01–AU10 и QR01–QR15 — план приёмки будущих сценариев. Текущие тесты покрывают
часть ограничений хранения, но не заявляют выполнение всего этого плана.
Порты GitReader/CommentPublisher/ReviewModel/PaymentGateway и repositories будут
введены с конкретными сценариями; сейчас реализован только контракт UnitOfWork.
