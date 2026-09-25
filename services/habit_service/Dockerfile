FROM python:3.11-slim

WORKDIR /app

COPY services/habit_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/habit_service /app/services/habit_service

CMD ["uvicorn", "services.habit_service.main:app", "--host", "0.0.0.0", "--port", "8004"]

