# Матрикс — персонаж растёт, когда ты ходишь на пары

Чат-бот и мини-приложение в **MAX** для студентов 1–2 курса колледжа или вуза. Трек хакатона — «Образовательные решения».

## Назначение

Первые месяцы учёбы решают многое. Студент 1–2 курса хочет привыкнуть регулярно ходить на занятия и вовремя сдавать задания. Эмоциональной обратной связи ему при этом не хватает, мотивация быстро падает. Он пропускает пары, копит долги и в итоге рискует отчислением.

«Матрикс» даёт немедленную эмоциональную обратную связь за учебную дисциплину:

- студент отмечается на паре за секунды — по QR-коду или коду с экрана преподавателя;
- его 3D-персонаж сразу реагирует, растёт и получает новые образы;
- бот MAX присылает подтверждение с наградой;
- куратор видит посещаемость группы и тех, у кого падает вовлечённость.

Целевая аудитория и границы MVP описаны в [docs/SCOPE.md](docs/SCOPE.md), дизайн-система — в [docs/DESIGN.md](docs/DESIGN.md).

## Основной пользовательский сценарий

1. Преподаватель открывает пару в админ-панели (кнопка «Код»). На экране появляются QR-код и 4-значный код, оба меняются каждые 30 секунд.
2. Студент отмечается одним из трёх способов:
   - сканирует QR камерой — открывается мини-приложение MAX (`https://max.ru/<бот>?startapp=att-<id>-<код>`) и сразу отмечает;
   - в мини-приложении на экране «Сегодня» нажимает «Сканировать QR» или вводит код;
   - отправляет боту `/checkin 1234`.
3. **Reward Service** начисляет монеты, очки интеллекта и настроение персонажа. Начисление пишется в журнал.
4. Персонаж на экране «Сегодня» танцует, появляются «+N», шкалы растут. При росте уровня персонаж физически растёт, а за посещения открываются новые образы и локации.
5. Бот MAX присылает уведомление: награда, настроение персонажа, серия посещений и кнопка «Посмотреть на персонажа».

Если студент пропустил пару, бот предлагает взять «день без штрафа» (2 раза за 30 дней). Без этого персонаж немного грустит и серия прерывается.

### Мини-игра «Забег до пары»

На главном экране — раннер в духе Subway Surfers: персонаж студента бежит по кампусу (свайпы: полоса, прыжок через барьер, подкат под растяжку), собирает монеты и соревнуется с одногруппниками в недельном рейтинге.

- Игра привязана к учёбе: забегов с наградой в день 3, и каждая посещённая сегодня пара добавляет ещё 2. Сверх лимита можно играть на рейтинг без монет; монеты из игры ограничены дневным потолком.
- По итогам недели топ-3 группы получают призовые монеты, бот пишет победителям и публикует итоги в чате группы (кнопка «Играть» открывает игру: `?startapp=game`).
- Очки считает сервер (дистанция + монеты × 5) и проверяет правдоподобие: дистанция не больше максимальной скорости × время, время — не больше реального с момента старта, у забега один финиш.
- API: `GET /api/competitions/games/runner/overview`, `…/leaderboard?scope=group|all`, `POST …/start`, `POST …/runs/{id}/finish`.

## Состав и архитектура

```
 MAX (чат-бот + мини-приложение)     Веб-версия / админка
          │  Bot API (long polling)          │  HTTPS
          ▼                                  ▼
   max-bot-service ───────────────► API Gateway (Caddy) ──► frontend (React + Three.js, nginx)
          ▲                                  │ /api/*
          │ уведомления                      ▼
   event-service ──► reward-service ──► user-service (монеты)
   (пары, коды, QR,      │              character-service (персонаж, сеты, снимки)
    серии, импорт)       │              achievement-service (достижения)
                         └────────────► notification-service (WebSocket во фронтенд)
   statistics-service (дашборд куратора), task/habit/inventory/social/economy/competition-services
                                     │
                                PostgreSQL 15
```

| Сервис | Порт | Назначение | Файл зависимостей |
|---|---|---|---|
| `gateway` (Caddy) | 80 / 443 | Единая точка входа, CORS, закрытие внутренних маршрутов | — (образ `caddy:2-alpine`) |
| `frontend` | 3000 | Мини-приложение и веб-версия (React, Vite, Three.js), админ-панель `/admin` | `frontend/package.json` + `package-lock.json` |
| `user-service` | 8001 | Пользователи, монеты, вход по MAX initData, роли | `services/user_service/requirements.txt` |
| `character-service` | 8002 | Персонаж, настроение, рост, кастомизация, ежедневные снимки | `services/character_service/requirements.txt` |
| `task-service` | 8003 | Задачи и цели (AI-оценка, есть заглушка) | `services/task_service/requirements.txt` |
| `habit-service` | 8004 | Привычки | `services/habit_service/requirements.txt` |
| `inventory-service` | 8005 | Предметы, лутбоксы, обмен | `services/inventory_service/requirements.txt` |
| `achievement-service` | 8006 | Достижения, в т.ч. за посещаемость | `services/achievement_service/requirements.txt` |
| `social-service` | 8007 | Друзья и учебные группы | `services/social_service/requirements.txt` |
| `event-service` | 8008 | **Пары, ротируемые коды и QR, отметка, серии, «день без штрафа», импорт расписания** | `services/event_service/requirements.txt` |
| `economy-service` | 8009 | Магазин | `services/economy_service/requirements.txt` |
| `competition-service` | 8010 | Соревнования и челленджи | `services/competition_service/requirements.txt` |
| `reward-service` | 8011 | **Централизованное начисление наград и журнал** (только внутри сети) | `services/reward_service/requirements.txt` |
| `statistics-service` | 8012 | Статистика, лидерборды, **дашборд куратора** | `services/statistics_service/requirements.txt` |
| `notification-service` | 8013 | WebSocket-события во фронтенд | `services/notification_service/requirements.txt` |
| `max-bot-service` | 8020 | Чат-бот MAX: команды, диплинки, уведомления | `services/max_bot_service/requirements.txt` |
| `postgres` | 5432 | Общая база данных | — (образ `postgres:15`) |
| `loki` / `promtail` / `grafana` | 3100 / — / 3001 | Логи и мониторинг (необязательно для сценария) | — |

Общий код лежит в `services/shared/`:

- `attendance_codes.py` — коды отметки: TOTP-подобная схема HMAC(секрет пары, номер окна), принимаются текущее и предыдущее окно;
- `max_auth.py` — проверка подписи initData по алгоритму MAX;
- `streaks.py` — серии посещений;
- `auth.py` — зависимости авторизации;
- `migrations.py` — идемпотентная миграция схемы.

## Запуск одной командой

```bash
cp .env.example .env
docker compose up --build -d
```

После запуска:

| Что | Адрес |
|---|---|
| Приложение (веб-версия) | <http://localhost> |
| Админ-панель | <http://localhost/admin> (токен — `ADMIN_TOKEN` из `.env`) |
| Swagger всех сервисов | <http://localhost/docs> |
| Grafana | <http://localhost:3001> |

**Демо-данные** — смоделированные: группа, 10 студентов, история за 3 недели, идущая пара, пропуск для «дня без штрафа».

```bash
docker compose exec user-service python -m scripts.seed_demo
```

Сборка без кеша на машине разработчика занимает меньше 5 минут, без учёта первичной загрузки базовых образов. Контекст сборки ограничен `.dockerignore`.

## Переменные окружения

Все переменные перечислены в [.env.example](.env.example). Рабочих токенов и паролей в репозитории нет.

| Переменная | Обязательна | Назначение |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | да | Доступ к БД. Без пароля compose не запустится |
| `MAX_BOT_TOKEN` | для бота | Токен чат-бота MAX. Без него всё, кроме бота, работает |
| `MAX_BOT_USERNAME` | для QR | Ник бота для диплинков `https://max.ru/<ник>?startapp=…` |
| `WEBAPP_URL` | для бота | HTTPS-адрес мини-приложения — запасная кнопка, если ник не задан |
| `MAX_OPEN_APP_MODE` | нет | `link` (по умолчанию) или `open_app` — формат кнопки открытия мини-приложения |
| `ADMIN_TOKEN` | да (прод) | Токен администратора/куратора (заголовок `X-Admin-Token`). Если пусто — проверка отключена, только для локальной отладки |
| `AUTH_MODE` | нет | `lenient` — веб-демо может передавать `?user_id=`; `strict` — только подписанный initData MAX |
| `CHECKIN_REQUIRE_MAX_AUTH` | нет | `true` — отметка только из мини-приложения MAX с подписью |
| `ALLOW_DB_RESET` | нет | Разрешить эндпоинт полной очистки БД (только тестовые стенды) |
| `APP_UTC_OFFSET_HOURS` | нет | Часовой пояс расписания, по умолчанию 3 (Москва) |
| `LESSON_CODE_WINDOW_SECONDS` | нет | Период смены кода, по умолчанию 30 |
| `CHECKIN_ENFORCE_WINDOW` | нет | Отметка только во время пары ±15 минут |
| `STREAK_FREEZES_PER_30D`, `STREAK_FREEZE_DECISION_MIN`, `STREAK_MISS_GRACE_MIN`, `MISSED_LESSON_SATISFACTION_PENALTY` | нет | Правила серии и «дня без штрафа» |
| `GAME_BASE_RUNS`, `GAME_RUNS_PER_LESSON`, `GAME_PICKUPS_PER_COIN`, `GAME_MAX_COINS_PER_RUN`, `GAME_DAILY_COIN_CAP`, `GAME_WEEKLY_PRIZES` | нет | Правила мини-игры: попытки с наградой, курс монет, лимиты, недельные призы |
| `LLM_PROVIDER`, `OPENROUTER_API_KEY`, `OLLAMA_*` | нет | AI-оценка задач. Без ключа работает детерминированная заглушка |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | да | Вход в Grafana |
| `SQL_ECHO` | нет | Логирование SQL (отладка) |

## Внешние сервисы и интеграции

| Интеграция | Обязательна для проверки | Как проверить без неё |
|---|---|---|
| **MAX Bot API** (`platform-api.max.ru`) — сообщения, команды, диплинки | да, основной сценарий доступен в MAX | Веб-версия <http://localhost> проходит тот же сценарий; уведомления видны в логах `max-bot-service` |
| **MAX Bridge** (`st.max.ru/js/max-web-app.js`) — вход по initData, `openCodeReader` (сканер QR), `HapticFeedback`, `BackButton`, `start_param` | да, внутри MAX | Вне MAX используется вход по нику и ввод кода вручную |
| OpenRouter / Ollama (LLM) | нет | Заглушка оценки задач |
| Google Fonts (Manrope, Inter) | нет | Системный шрифт |

## Работа с данными

- Все сервисы работают с одной PostgreSQL. Схема создаётся при старте (`create_all`). Доработки добавляет идемпотентная миграция `services/shared/migrations.py`: она сначала читает каталог, использует `lock_timeout` и advisory-lock.
- Персональные данные — только ник и числовой id MAX (email вида `max_<id>@max.local` служебный). Целевая аудитория 18+.
- Начисления записываются в `transactions` с источником (`source`: `lesson_attendance`, `achievement`, `lesson_missed`, …).
- Для дашборда куратора `character_snapshots` раз в сутки сохраняет настроение и уровень.

### Тестовые и смоделированные данные

Требование п. 10 ограничений ТЗ:

- **Реальной интеграции с системой вуза нет.** Расписание загружается из тестового CSV или JSON: админка → «Тестовое расписание», `POST /api/events/lessons/import`, образцы в [data/](data/). Такие занятия помечены `is_simulated=true` и показываются с бейджем **«Тестовые данные»**.
- `scripts/seed_demo.py` создаёт **смоделированных** студентов и историю посещений для демонстрации дашборда куратора.

## Пошаговая проверка основного сценария

1. `cp .env.example .env` → `docker compose up --build -d` → `docker compose exec user-service python -m scripts.seed_demo`.
2. Откройте <http://localhost/admin>, введите `ADMIN_TOKEN`. В разделе «Пары и события» найдите «Демо: Математический анализ» и нажмите «Код»: появятся QR и код.
3. В другой вкладке откройте <http://localhost>, войдите под ником `demo_ivan`. Экран «Сегодня»: персонаж, карточка «Идёт сейчас».
4. Введите неверный код → под полем появится понятная ошибка.
5. Введите код с экрана админки → «Отметиться». Ожидаемо:
   - тост «Посещение отмечено! +5 монет · +15 интеллекта · +8 настроения»;
   - тост «Открыт новый сет: Эрудит»;
   - персонаж танцует, шкала настроения растёт, карточка сменяется на «Вы отмечены».
6. Повторите отметку → «Вы уже отмечены», награда второй раз не начисляется.
7. «👕 Гардероб» → выберите «Эрудит»: на персонаже появится шапка выпускника.
8. Под ником `demo_student` на карточке пропуска нажмите «Без штрафа» → остаток «заморозок» уменьшится.
9. Админка → «Куратор»: посещаемость группы, студенты в зоне риска, динамика по неделям.
10. В MAX: откройте бота → `/start` → «Открыть Матрикс» (вход автоматический) или отсканируйте QR с экрана преподавателя. Отметка пройдёт сразу, в чат придёт уведомление.

Проверка через API (`curl`):

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost/api/events/lessons/<id>/qr
curl -X POST "http://localhost/api/events/lessons/<id>/check-in?user_id=<uid>" -H "Content-Type: application/json" -d '{"code":"<код>","method":"code"}'
```

Контракт обязательных проверок — [DATA-API.yaml](DATA-API.yaml), спецификация — [docs/openapi.json](docs/openapi.json) (генерируется `python scripts/export_openapi.py`).

## Примеры ожидаемого поведения

Ответ отметки (`POST /api/events/lessons/13/check-in`, сокращено):

```json
{
  "status": "checked_in",
  "message": "Посещение отмечено! Награды начислены.",
  "rewards": {"coins": 5, "intelligence_points": 15, "satisfaction": 8},
  "rewards_status": "granted",
  "character": {"satisfaction_before": 62, "satisfaction": 70, "mood": "happy", "mood_label": "доволен", "level_up": false},
  "streak": {"current": 13, "best": 13, "freezes_available": 2},
  "achievements_earned": [{"achievement_name": "Первая пара"}]
}
```

Уведомление бота в MAX:

```
✅ Посещение отмечено: Демо: Математический анализ
Награда: +5 🪙  +15 🧠  +8 😊
Персонаж доволен 😊 (62 → 70)
🔥 Серия посещений: 13
[🎉 Посмотреть на персонажа] [🔥 Моя серия] [🎮 Персонаж]
```

Ошибки возвращаются с понятным `detail`:

| Статус | `detail` |
|---|---|
| 400 | «Неверный или устаревший код. Введите код, который сейчас на экране преподавателя.» |
| 403 | «Вы не состоите в группе этого занятия» |
| 429 | «Слишком много неверных попыток» |

Внутренние маршруты (`/api/rewards/*`, начисление монет, рассылки бота) снаружи отвечают `404`.

## Тесты

```bash
pip install -r services/requirements-test.txt
pytest services --import-mode=importlib
```

Новые тесты:

| Файл | Что проверяет |
|---|---|
| `services/shared/tests` | Коды, подпись initData, серии |
| `services/event_service/tests/test_lesson_checkin.py` | Отметка, QR, «заморозка», импорт |
| `services/character_service/tests/test_appearance.py` | Кастомизация |
| `services/statistics_service/tests/test_curator.py` | Дашборд куратора |
| `services/user_service/tests/test_max_login.py` | Вход через MAX, роли |
| `services/max_bot_service/tests` | Бот |
| `services/reward_service/tests` | Журнал начислений |

Смоук-проверка чат-бота без реального MAX (обработчики работают с настоящими сервисами, вместо MAX API — заглушка, печатающая сообщения и кнопки):

```bash
docker compose cp scripts/bot_smoke.py max-bot-service:/app/bot_smoke.py
docker compose exec max-bot-service python /app/bot_smoke.py <max_user_id> <lesson_id> <код>
```

Часть старых тестов (кланы, соревнования, магазин) устарела относительно кода и падала ещё до доработок. Это отражено в «Известных ограничениях».

## Известные ограничения

- **Авторизация.** WebSocket `/ws/{user_id}` не требует авторизации. В режиме `AUTH_MODE=lenient` часть старых эндпоинтов доверяет `?user_id=` — это нужно для веб-демо. Для пилота включите `AUTH_MODE=strict` и `CHECKIN_REQUIRE_MAX_AUTH=true`.
- **Не проверено на устройстве.**
  - Payload события `bot_started` из диплинка `?start=` (запасной путь — текст `/start att-…`).
  - Формат нативной кнопки `open_app`: по умолчанию используется ссылка `?startapp=`.
  - Открывает ли системная камера мини-приложение по ссылке `max.ru`: гарантированный путь — «Сканировать QR» внутри приложения.
- **Сканер QR.** `openCodeReader` доступен только в мобильном MAX. В веб-версии MAX и в браузере отметка идёт вводом кода, остальной сценарий тот же.
- **Лимит попыток ввода кода** хранится в памяти процесса, поэтому рассчитан на один экземпляр `event-service`.
- **3D-образы и окружения** процедурные: аксессуары, свет, цвета комнаты. Структура пресетов (`frontend/src/features/character/appearance/presets.js`) позволяет подключить отдельные GLB-модели без изменения API.
- **Старые тесты.** 48 из них (кланы, соревнования, часть экономики и инвентаря) не соответствуют текущему коду и падали до доработок.
- **Видео-подсказки аватара (TTS + рендер)** не реализованы — это направление развития, см. [docs/PRESENTATION.md](docs/PRESENTATION.md).

## Остановка и повторный запуск

```bash
docker compose stop            # остановить, данные сохраняются
docker compose start           # запустить снова
docker compose down            # удалить контейнеры (том с БД сохраняется)
docker compose down -v         # удалить контейнеры и все данные (чистый старт)
docker compose up --build -d   # пересобрать после изменений кода
docker compose logs -f event-service max-bot-service   # логи основного сценария
```

Продакшен-конфигурация (домен, HTTPS, без проброса внутренних портов) — `docker-compose.prod.yml` и `gateway/Caddyfile.prod`, см. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Документация

- [docs/SCOPE.md](docs/SCOPE.md) — аудит, MoSCoW, найденные проблемы и допущения.
- [docs/DESIGN.md](docs/DESIGN.md) — дизайн-система и редизайн.
- [docs/PRESENTATION.md](docs/PRESENTATION.md) — структура презентации для защиты.
- [MICROSERVICES_README.md](MICROSERVICES_README.md) — подробности по сервисам.
- [database_diagram.md](database_diagram.md) — схема БД.
