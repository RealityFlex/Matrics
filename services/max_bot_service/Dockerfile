FROM python:3.11-slim

WORKDIR /app

# Копируем requirements
COPY services/max_bot_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем shared модули
COPY services/shared /app/services/shared

# Копируем сервис
COPY services/max_bot_service /app/services/max_bot_service

# Запуск
CMD ["uvicorn", "services.max_bot_service.main:app", "--host", "0.0.0.0", "--port", "8020"]

