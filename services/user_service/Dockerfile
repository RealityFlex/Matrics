FROM python:3.11-slim

WORKDIR /app

# Копируем requirements
COPY services/user_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем shared модули
COPY services/shared /app/services/shared

# Копируем scripts (нужно для импорта стандартных предметов)
COPY scripts /app/scripts

# Копируем сервис
COPY services/user_service /app/services/user_service

# Запуск
CMD ["uvicorn", "services.user_service.main:app", "--host", "0.0.0.0", "--port", "8001"]

