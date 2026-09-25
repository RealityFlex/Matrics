# Тамагочи-Метавселенная - Микросервисная Архитектура

## 🏗️ Архитектура

Приложение разделено на **14 микросервисов** + **API Gateway** + **PostgreSQL**. Все сервисы реализованы; актуальное описание запуска — в [README.md](README.md).

```
┌─────────────┐
│   Caddy     │  API Gateway (порт 80/443)
│  Gateway    │  
└──────┬──────┘
       │
       ├──────────┐
       │          │
┌──────▼──────┐  ┌▼──────────────┐
│ PostgreSQL  │  │ Микросервисы  │
│   (5432)    │◄─┤  (8001-8012)  │
└─────────────┘  └───────────────┘
```

## 📦 Микросервисы

### 1. **User Service** (порт 8001)
- Управление пользователями (CRUD)
- Профиль пользователя
- Управление монетами

### 2. **Character Service** (порт 8002)  
- Управление персонажами
- Расчет рейтинга: `intelligence_points + satisfaction / 2 + intelligence_level × 100`
- Настроение (mood) и стадия роста (growth_stage), кастомизация: 5 образов и 5 локаций с разблокировкой за учёбу
- Ежедневные снимки параметров (`character_snapshots`) для дашборда куратора
- Изменение удовлетворения (0-100)
- Логика интеллекта с автоматическим повышением уровня

### 3. **Task Service** (порт 8003) ✅
- CRUD задач
- Завершение задачи → вызов Reward Service
- Статистика по задачам

### 4. **Habit Service** (порт 8004) ✅
- CRUD привычек
- Логирование выполнения → вызов Reward Service
- Статистика серий (streaks)

### 5. **Inventory Service** (порт 8005) ✅
- Управление предметами (CRUD)
- Инвентарь пользователя
- Перенос предметов между пользователями

### 6. **Achievement Service** (порт 8006) ✅
- CRUD достижений
- Автоматическая проверка условий
- Выдача наград за достижения

### 7. **Social Service** (порт 8007) ✅
- Система дружбы
- Учебные группы и приглашения (группы определяют, кому показываются пары)
- Кланы — только модели, API нет (вне scope)

### 8. **Event Service** (порт 8008) ✅
- CRUD мероприятий и занятий (пар)
- **Отметка на паре**: ротируемый код (TOTP-подобный, 30 с) и QR-диплинк на мини-приложение MAX
- Серии посещений и «день без штрафа» (streak freeze), воркер пропусков
- Тестовый импорт расписания (CSV/JSON, помечается как смоделированные данные)

### 9. **Economy Service** (порт 8009) ✅
- Магазин (листинги)
- Покупка/продажа предметов
- История транзакций

### 10. **Competition Service** (порт 8010) ✅
- CRUD соревнований
- Подсчет результатов
- Таблица лидеров

### 11. **Reward Service** (порт 8011) ✅
- **Централизованная выдача наград**
- Выдача монет
- Выдача очков интеллекта
- Выдача предметов
- Проверка достижений

### 12. **Statistics Service** (порт 8012) ✅
- Сводная статистика пользователя и лидерборды
- **Дашборд куратора**: посещаемость группы, риск-лист, динамика по неделям

### 13. **Notification Service** (порт 8013) ✅
- WebSocket `/ws/{user_id}`: события параметров, достижений, отметок во фронтенд

### 14. **MAX Bot Service** (порт 8020) ✅
- Чат-бот MAX (long polling): команды `/start`, `/checkin`, `/streak`, `/character` и др.
- Диплинки `?start=att-…`, кнопка открытия мини-приложения, уведомления

### API Gateway (Caddy) ✅
- Единая точка входа
- Роутинг: `/api/{service}/*` → соответствующий сервис
- Внутренние межсервисные маршруты закрыты (404)
- CORS настройки
- Логирование

## 🚀 Быстрый старт

### Предварительные требования
- Docker & Docker Compose
- Python 3.11+ (для локальной разработки)

### Запуск всей системы

```bash
# 1. Клонировать репозиторий
cd Max

# 2. Запустить все сервисы
docker-compose up -d

# 3. Проверить статус
docker-compose ps

# 4. Просмотр логов
docker-compose logs -f [service-name]
```

### Доступ к API

- **API Gateway**: http://localhost
- **User Service**: http://localhost/api/users/ или http://localhost:8001
- **Character Service**: http://localhost/api/characters/ или http://localhost:8002
- **Reward Service**: http://localhost/api/rewards/ или http://localhost:8011

### Swagger документация

Каждый сервис имеет свою документацию:
- User Service: http://localhost:8001/docs
- Character Service: http://localhost:8002/docs
- Reward Service: http://localhost:8011/docs

## 📋 Примеры использования

### 1. Создание пользователя и персонажа

```bash
# Создать пользователя
curl -X POST http://localhost/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "player1", "email": "player1@example.com"}'

# Ответ: {"id": 1, "username": "player1", "email": "player1@example.com", "coins": 0}

# Создать персонажа
curl -X POST http://localhost/api/characters/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "name": "MyHero"}'

# Ответ: {"id": 1, "user_id": 1, "name": "MyHero", "satisfaction": 50, "intelligence_level": 1, "rating": 115.0}
```

### 2. Выдача наград через Reward Service

```bash
# Выдать награды (монеты + очки интеллекта)
curl -X POST http://localhost/api/rewards/grant \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "coins": 100,
    "intelligence_points": 50
  }'

# Ответ:
# {
#   "user_id": 1,
#   "coins_added": 100,
#   "intelligence_added": 50,
#   "level_up": false,
#   "achievements_earned": []
# }
```

### 3. Проверка рейтинга персонажа

```bash
curl http://localhost/api/characters/1/rating

# Ответ:
# {
#   "character_id": 1,
#   "rating": 115.0,
#   "satisfaction": 50,
#   "intelligence_level": 1,
#   "bonus_points": 0
# }
```

## 🔄 Бизнес-логика

### Сценарий: Завершение задачи

```
User завершает задачу
    ↓
Task Service → Reward Service
    ↓
Reward Service:
  1. Добавляет монеты (User Service)
  2. Добавляет очки интеллекта (Character Service)
  3. Проверяет достижения (Achievement Service)
    ↓
Возвращает результат с информацией о наградах
```

### Сценарий: Покупка в магазине

```
User покупает предмет
    ↓
Economy Service проверяет:
  - Наличие монет (User Service)
  - Доступность товара (Inventory Service)
    ↓
Выполняет транзакцию:
  - Списывает монеты у покупателя
  - Добавляет монеты продавцу
  - Переносит предмет в инвентарь
  - Создает запись транзакции
```

## 🛠️ Разработка

### Структура проекта

```
Max/
├── services/
│   ├── shared/                  # Общий код
│   │   ├── database.py          # Подключение к БД
│   │   ├── models/              # SQLAlchemy модели
│   │   ├── schemas/             # Pydantic схемы
│   │   └── utils.py             # HTTP клиент
│   ├── user_service/            # ✅ Реализован
│   ├── character_service/       # ✅ Реализован
│   ├── reward_service/          # ✅ Реализован
│   ├── task_service/            # ✅ Реализован
│   ├── habit_service/           # ✅ Реализован
│   ├── inventory_service/       # ✅ Реализован
│   ├── achievement_service/     # ✅ Реализован
│   ├── social_service/          # ✅ Реализован
│   ├── event_service/           # ✅ Реализован
│   ├── economy_service/         # ✅ Реализован
│   ├── competition_service/     # ✅ Реализован
│   └── statistics_service/      # ✅ Реализован
├── gateway/
│   └── Caddyfile                # ✅ Настроен
├── docker-compose.yml           # ✅ Создан
└── MICROSERVICES_README.md      # Эта документация
```

### Создание нового сервиса

1. **Создайте структуру:**
```bash
mkdir -p services/new_service
touch services/new_service/__init__.py
touch services/new_service/main.py
touch services/new_service/requirements.txt
touch services/new_service/Dockerfile
```

2. **Используйте шаблон** (см. user_service/main.py)

3. **Добавьте в docker-compose.yml:**
```yaml
new-service:
  build:
    context: .
    dockerfile: services/new_service/Dockerfile
  container_name: new_service
  environment:
    DATABASE_URL: postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db
  ports:
    - "80XX:80XX"
  depends_on:
    postgres:
      condition: service_healthy
  networks:
    - tamagotchi_network
```

4. **Добавьте роутинг в Caddyfile:**
```
handle_path /api/newservice/* {
    reverse_proxy new-service:80XX
}
```

### Межсервисное взаимодействие

Используйте `ServiceClient` из `services/shared/utils.py`:

```python
from services.shared.utils import ServiceClient

# В эндпоинте
user_service = ServiceClient("user")
try:
    user_data = await user_service.get(f"/users/{user_id}")
    # Работа с данными
finally:
    await user_service.close()
```

## 🗄️ База данных

Все сервисы используют **единую PostgreSQL базу данных**.

### Переменная окружения
```
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db
```

### Модели
Все модели находятся в `services/shared/models/`:
- user.py
- character.py
- task.py, habit.py
- item.py, achievement.py
- social.py, event.py, economy.py

## 🧪 Тестирование

```bash
# Запустить конкретный сервис локально
cd services/user_service
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8001

# Тестирование через curl
curl http://localhost:8001/health
```

## 📊 Мониторинг

### Проверка здоровья сервисов
```bash
# Через API Gateway
curl http://localhost/health

# Напрямую к сервисам
curl http://localhost:8001/health  # User Service
curl http://localhost:8002/health  # Character Service
curl http://localhost:8011/health  # Reward Service
```

### Логи
```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f user-service

# API Gateway
docker-compose logs -f gateway
```

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db
```

### Порты сервисов
- 8001 - User Service
- 8002 - Character Service
- 8003 - Task Service
- 8004 - Habit Service
- 8005 - Inventory Service
- 8006 - Achievement Service
- 8007 - Social Service
- 8008 - Event Service
- 8009 - Economy Service
- 8010 - Competition Service
- 8011 - Reward Service
- 8012 - Statistics Service
- 8013 - Notification Service
- 8020 - MAX Bot Service

## 📝 Направления развития

- [x] Все 14 микросервисов реализованы
- [x] Минимальная авторизация: подписанный initData MAX, `X-Admin-Token`, закрытие внутренних маршрутов на gateway
- [ ] Полноценная авторизация (JWT) для всех сервисов и WebSocket
- [ ] Rate limiting на gateway, кэширование (Redis), очередь событий вместо синхронных HTTP-вызовов
- [ ] Миграции через Alembic вместо стартового DDL

## 🤝 Вклад в разработку

1. Используйте существующие сервисы (User, Character, Reward) как примеры
2. Следуйте единообразной структуре
3. Используйте shared модули для моделей и утилит
4. Документируйте API в Swagger
5. Обновляйте docker-compose.yml и Caddyfile

## 📄 Лицензия

MIT

---

**Статус реализации:** 14 из 14 микросервисов + инфраструктура (Docker Compose, Caddy, Grafana/Loki) ✅

