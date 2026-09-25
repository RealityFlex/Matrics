# 🚀 Руководство по развертыванию Tamagotchi Metaverse

## 📋 Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Требования](#требования)
3. [Быстрый старт](#быстрый-старт)
4. [Детальная настройка](#детальная-настройка)
5. [Тестирование](#тестирование)
6. [Решение проблем](#решение-проблем)

## 🏗️ Обзор архитектуры

Система состоит из 12 микросервисов, единой базы данных PostgreSQL и API Gateway (Caddy):

### Микросервисы
| Сервис | Порт | Описание |
|--------|------|----------|
| User Service | 8001 | Управление пользователями |
| Character Service | 8002 | Управление персонажами (рейтинг, удовлетворение, интеллект) |
| Task Service | 8003 | Управление задачами |
| Habit Service | 8004 | Управление привычками |
| Inventory Service | 8005 | Управление предметами и инвентарем |
| Achievement Service | 8006 | Управление достижениями |
| Social Service | 8007 | Управление социальными взаимодействиями (кланы, дружба, группы) |
| Event Service | 8008 | Управление событиями и посещаемостью |
| Economy Service | 8009 | Управление магазином и транзакциями |
| Competition Service | 8010 | Управление соревнованиями |
| Reward Service | 8011 | Централизованная выдача наград |
| Statistics Service | 8012 | Агрегация статистики |

### Инфраструктура
- **PostgreSQL** (порт 5432): Единая база данных для всех сервисов
- **API Gateway** (порт 80): Caddy для маршрутизации запросов

## 🔧 Требования

### Обязательные
- Docker >= 20.10
- Docker Compose >= 2.0
- 4GB+ свободной оперативной памяти
- 10GB+ свободного места на диске

### Рекомендуемые
- Docker >= 24.0
- Docker Compose >= 2.20
- 8GB+ оперативной памяти
- SSD диск

## ⚡ Быстрый старт

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd Max
```

### 2. Запуск всей системы
```bash
# Собрать и запустить все сервисы
docker-compose up --build

# Или в фоновом режиме
docker-compose up --build -d
```

### 3. Проверка работоспособности
```bash
# Проверить статус всех контейнеров
docker-compose ps

# Проверить логи
docker-compose logs -f

# Проверить API Gateway
curl http://localhost/health
```

### 4. Доступ к сервисам

**Через API Gateway:**
- http://localhost/api/users/
- http://localhost/api/characters/
- http://localhost/api/tasks/
- http://localhost/api/habits/
- http://localhost/api/inventory/
- http://localhost/api/achievements/
- http://localhost/api/social/
- http://localhost/api/events/
- http://localhost/api/economy/
- http://localhost/api/competitions/
- http://localhost/api/rewards/
- http://localhost/api/statistics/

**Прямой доступ к сервисам:**
- User Service: http://localhost:8001
- Character Service: http://localhost:8002
- Task Service: http://localhost:8003
- Habit Service: http://localhost:8004
- Inventory Service: http://localhost:8005
- Achievement Service: http://localhost:8006
- Social Service: http://localhost:8007
- Event Service: http://localhost:8008
- Economy Service: http://localhost:8009
- Competition Service: http://localhost:8010
- Reward Service: http://localhost:8011
- Statistics Service: http://localhost:8012

## 🛠️ Детальная настройка

### Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# База данных
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=tamagotchi_db
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db

# Сервисы
USER_SERVICE_PORT=8001
CHARACTER_SERVICE_PORT=8002
TASK_SERVICE_PORT=8003
HABIT_SERVICE_PORT=8004
INVENTORY_SERVICE_PORT=8005
ACHIEVEMENT_SERVICE_PORT=8006
SOCIAL_SERVICE_PORT=8007
EVENT_SERVICE_PORT=8008
ECONOMY_SERVICE_PORT=8009
COMPETITION_SERVICE_PORT=8010
REWARD_SERVICE_PORT=8011
STATISTICS_SERVICE_PORT=8012
```

### Запуск отдельных сервисов

```bash
# Только база данных
docker-compose up postgres

# Конкретный сервис
docker-compose up user-service

# Несколько сервисов
docker-compose up user-service character-service reward-service
```

### Масштабирование

```bash
# Запустить несколько экземпляров сервиса
docker-compose up --scale user-service=3

# Остановить сервисы
docker-compose down

# Остановить и удалить volumes
docker-compose down -v
```

## 🧪 Тестирование

### Тестирование API

#### 1. Создание пользователя
```bash
curl -X POST http://localhost/api/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com"
  }'
```

#### 2. Создание персонажа
```bash
curl -X POST http://localhost/api/characters/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "name": "MyCharacter"
  }'
```

#### 3. Создание задачи
```bash
curl -X POST "http://localhost/api/tasks/?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Task",
    "description": "Test Description",
    "priority": "high",
    "reward_coins": 100,
    "reward_intelligence_points": 10
  }'
```

#### 4. Завершение задачи (с выдачей наград)
```bash
curl -X POST http://localhost/api/tasks/1/complete
```

#### 5. Получение сводной статистики пользователя
```bash
curl http://localhost/api/statistics/stats/users/1/summary
```

### Использование Postman

Импортируйте эндпоинты из документации сервисов:
- http://localhost:8001/docs (User Service)
- http://localhost:8002/docs (Character Service)
- и т.д.

## 🔍 Решение проблем

### Контейнер не запускается

```bash
# Проверить логи конкретного сервиса
docker-compose logs user-service

# Проверить ошибки при сборке
docker-compose build --no-cache user-service

# Пересоздать контейнер
docker-compose up --force-recreate user-service
```

### База данных недоступна

```bash
# Проверить статус PostgreSQL
docker-compose ps postgres

# Подключиться к базе данных
docker-compose exec postgres psql -U user -d tamagotchi_db

# Проверить логи БД
docker-compose logs postgres
```

### Проблемы с сетью

```bash
# Пересоздать сеть
docker-compose down
docker network prune
docker-compose up
```

### Очистка всех данных

```bash
# Остановить все сервисы
docker-compose down

# Удалить volumes
docker-compose down -v

# Удалить все образы
docker-compose down --rmi all

# Полная очистка (осторожно!)
docker system prune -a --volumes
```

## 📊 Мониторинг

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f user-service

# Последние N строк
docker-compose logs --tail=100 user-service
```

### Статистика ресурсов

```bash
# Использование ресурсов
docker stats

# Проверка занятого места
docker system df
```

## 🔄 Обновление сервисов

```bash
# Пересобрать один сервис
docker-compose build user-service
docker-compose up -d user-service

# Пересобрать все сервисы
docker-compose build
docker-compose up -d
```

## 📝 Миграции базы данных

База данных инициализируется автоматически при первом запуске через `init_db()` в каждом сервисе. SQLAlchemy создаст все необходимые таблицы.

### Сброс базы данных

```bash
# Остановить все сервисы
docker-compose down

# Удалить volume с данными БД
docker volume rm max_postgres_data

# Перезапустить
docker-compose up -d
```

## 🔐 Безопасность

⚠️ **Важно**: Текущая конфигурация предназначена для разработки!

Для продакшена:
1. Измените пароли в `.env`
2. Включите HTTPS в Caddy
3. Добавьте аутентификацию/авторизацию
4. Настройте firewall
5. Используйте secrets для чувствительных данных

## 📚 Дополнительная документация

- [MICROSERVICES_README.md](./MICROSERVICES_README.md) - Подробная документация по архитектуре
- [QUICKSTART.md](./QUICKSTART.md) - Быстрый старт для разработчиков
- [database_diagram.md](./database_diagram.md) - ERD диаграмма базы данных

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Перезапустите сервисы: `docker-compose restart`
4. Обратитесь к документации конкретного сервиса

---

**Версия**: 1.0.0  
**Последнее обновление**: 2025-11-05

