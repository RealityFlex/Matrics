# 📊 Система мониторинга логов

Система мониторинга логов на базе **Loki + Grafana + Promtail** для централизованного сбора, хранения и визуализации логов всех контейнеров проекта.

## 🏗️ Архитектура

```
┌─────────────────┐
│   Контейнеры    │
│  (Все сервисы)  │
└────────┬────────┘
         │ Логи
         ▼
┌─────────────────┐
│    Promtail     │  ← Сборщик логов
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      Loki       │  ← Хранилище логов
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Grafana      │  ← Визуализация
└─────────────────┘
```

## 🚀 Быстрый старт

### 1. Запуск системы мониторинга

Система мониторинга автоматически запускается вместе с остальными сервисами:

```bash
docker-compose up -d
```

### 2. Доступ к интерфейсам

- **Grafana**: http://localhost:3001
  - Логин: `admin`
  - Пароль: `admin`
  - ⚠️ **Важно**: При первом входе измените пароль!

- **Loki API**: http://localhost:3100
  - Используется для прямых запросов к Loki API

### 3. Просмотр логов в Grafana

#### Использование готового дашборда

1. Откройте Grafana: http://localhost:3001
2. Войдите с учетными данными (admin/admin)
3. Перейдите в раздел **Dashboards** (иконка папки в левом меню)
4. Откройте дашборд **"Логи всех сервисов"**
5. Дашборд автоматически загружается при запуске Grafana и содержит:
   - Панель со всеми логами всех сервисов
   - График количества логов по сервисам
   - График ошибок по сервисам
   - Отдельные панели для каждого сервиса
   - Переменную для фильтрации по сервисам

#### Использование Explore для кастомных запросов

1. Перейдите в раздел **Explore** (иконка компаса в левом меню)
2. Выберите источник данных **Loki**
3. Используйте LogQL для запросов:

#### Примеры запросов LogQL

**Все логи:**
```logql
{job=~".+"}
```

**Логи конкретного сервиса:**
```logql
{job="user-service"}
```

**Логи с ошибками:**
```logql
{job=~".+"} |= "error"
```

**Логи с уровнем ERROR:**
```logql
{job=~".+"} | json | level="ERROR"
```

**Логи за последний час:**
```logql
{job=~".+"} [1h]
```

**Фильтрация по контейнеру:**
```logql
{container="user_service"}
```

## 📋 Мониторинг сервисов

Все сервисы автоматически помечены метками для сбора логов:

- `logging=promtail` - метка для сбора логов
- `logging_jobname=<service-name>` - имя сервиса для группировки

### Список отслеживаемых сервисов

- `postgres` - База данных
- `user-service` - Сервис пользователей
- `character-service` - Сервис персонажей
- `task-service` - Сервис задач
- `habit-service` - Сервис привычек
- `inventory-service` - Сервис инвентаря
- `achievement-service` - Сервис достижений
- `social-service` - Социальный сервис
- `event-service` - Сервис событий
- `economy-service` - Экономический сервис
- `competition-service` - Сервис соревнований
- `statistics-service` - Сервис статистики
- `reward-service` - Сервис наград
- `api-gateway` - API Gateway (Caddy)
- `frontend` - Frontend приложение

## 🔍 Поиск и фильтрация логов

### Поиск по тексту

```logql
{job=~".+"} |= "database connection"
```

### Поиск по регулярному выражению

```logql
{job=~".+"} |~ "error|exception|failed"
```

### Исключение определенных записей

```logql
{job=~".+"} != "debug"
```

### Комбинация фильтров

```logql
{job="user-service"} |= "error" | json | level="ERROR"
```

## 📊 Создание дашбордов

### Создание нового дашборда

1. В Grafana перейдите в **Dashboards** → **New Dashboard**
2. Добавьте новую панель (Add → Visualization)
3. Выберите источник данных **Loki**
4. Настройте запрос LogQL
5. Выберите тип визуализации (Logs, Time series, и т.д.)

### Примеры панелей

**Панель логов всех сервисов:**
- Запрос: `{job=~".+"}`
- Тип: Logs

**График ошибок по времени:**
- Запрос: `sum(count_over_time({job=~".+"} |= "error" [1m]))`
- Тип: Time series

**Топ сервисов по количеству логов:**
- Запрос: `sum by (job) (count_over_time({job=~".+"} [5m]))`
- Тип: Bar gauge

## 🛠️ Управление системой мониторинга

### Просмотр статуса сервисов

```bash
# Статус всех сервисов мониторинга
docker-compose ps loki promtail grafana

# Логи Loki
docker-compose logs -f loki

# Логи Promtail
docker-compose logs -f promtail

# Логи Grafana
docker-compose logs -f grafana
```

### Перезапуск сервисов мониторинга

```bash
# Перезапуск всех сервисов мониторинга
docker-compose restart loki promtail grafana

# Перезапуск только Grafana
docker-compose restart grafana
```

### Остановка системы мониторинга

```bash
# Остановка всех сервисов мониторинга
docker-compose stop loki promtail grafana
```

### Очистка данных

```bash
# Остановка и удаление volumes (удалит все логи!)
docker-compose down -v

# Удаление только volume с логами Loki
docker volume rm max_loki_data

# Удаление только volume Grafana
docker volume rm max_grafana_data
```

## ⚙️ Конфигурация

### Loki

Конфигурация находится в `monitoring/loki-config.yaml`:
- Порт: 3100
- Хранилище: файловая система (volume `loki_data`)
- Схема хранения: TSDB

### Promtail

Конфигурация находится в `monitoring/promtail-config.yaml`:
- Собирает логи из всех контейнеров с меткой `logging=promtail`
- Отправляет логи в Loki
- Автоматически парсит JSON логи
- Извлекает уровни логирования

### Grafana

Конфигурация находится в `monitoring/grafana-datasources.yaml`:
- Автоматически настраивает источник данных Loki
- Порт: 3001 (внешний) → 3000 (внутренний)
- Данные сохраняются в volume `grafana_data`

## 🔐 Безопасность

⚠️ **Важно для продакшена:**

1. **Измените пароль Grafana** при первом входе
2. Настройте аутентификацию для доступа к Loki API
3. Ограничьте доступ к портам 3001 и 3100 через firewall
4. Используйте HTTPS для Grafana
5. Настройте резервное копирование данных Loki

### Изменение пароля Grafana

1. Войдите в Grafana
2. Перейдите в **Administration** → **Users and access** → **Users**
3. Выберите пользователя `admin`
4. Нажмите **Change password**

### Настройка переменных окружения

Можно изменить пароль через переменные окружения в `docker-compose.yml`:

```yaml
grafana:
  environment:
    - GF_SECURITY_ADMIN_USER=admin
    - GF_SECURITY_ADMIN_PASSWORD=your_secure_password
```

## 📈 Производительность

### Рекомендации

- **Хранение логов**: По умолчанию Loki хранит логи в файловой системе. Для продакшена рекомендуется использовать S3 или другой объектный storage.
- **Ретеншн**: Настройте политику хранения логов в `loki-config.yaml`
- **Ограничение ресурсов**: Добавьте limits для контейнеров в `docker-compose.yml`:

```yaml
loki:
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: '1'
```

## 🐛 Устранение неполадок

### Promtail не собирает логи

1. Проверьте, что контейнеры имеют метку `logging=promtail`:
```bash
docker inspect <container_name> | grep -A 5 Labels
```

2. Проверьте логи Promtail:
```bash
docker-compose logs promtail
```

3. Убедитесь, что Promtail имеет доступ к Docker socket

4. **На Windows**: Убедитесь, что Docker Desktop запущен и настроен для использования Linux контейнеров. Promtail собирает логи через Docker API, поэтому путь `/var/lib/docker/containers` должен быть доступен через виртуализацию Docker Desktop.

### Loki не принимает логи

1. Проверьте статус Loki:
```bash
curl http://localhost:3100/ready
```

2. Проверьте логи Loki:
```bash
docker-compose logs loki
```

3. Убедитесь, что Promtail может подключиться к Loki:
```bash
docker-compose exec promtail wget -O- http://loki:3100/ready
```

### Grafana не показывает логи

1. Проверьте, что источник данных Loki настроен:
   - **Configuration** → **Data sources** → **Loki**
   - URL должен быть: `http://loki:3100`

2. Проверьте подключение:
   - Нажмите **Save & test** в настройках источника данных

3. Проверьте запрос LogQL:
   - Используйте простой запрос: `{job=~".+"}`

### Логи не появляются в реальном времени

- Убедитесь, что используется правильный временной диапазон в Grafana
- Проверьте, что Promtail работает и собирает логи
- Убедитесь, что контейнеры генерируют логи

## 📚 Дополнительные ресурсы

- [Документация Loki](https://grafana.com/docs/loki/latest/)
- [Документация Promtail](https://grafana.com/docs/loki/latest/clients/promtail/)
- [Документация Grafana](https://grafana.com/docs/grafana/latest/)
- [LogQL - язык запросов Loki](https://grafana.com/docs/loki/latest/logql/)

## 💡 Полезные запросы LogQL

```logql
# Все логи за последние 15 минут
{job=~".+"} [15m]

# Ошибки в user-service
{job="user-service"} |= "error"

# Логи с уровнем ERROR или WARN
{job=~".+"} | json | level=~"ERROR|WARN"

# Количество логов по сервисам
sum by (job) (count_over_time({job=~".+"} [5m]))

# Топ 10 сервисов по количеству логов
topk(10, sum by (job) (count_over_time({job=~".+"} [1h])))
```

