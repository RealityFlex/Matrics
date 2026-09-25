FROM python:3.11-slim

WORKDIR /app

COPY services/achievement_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/achievement_service /app/services/achievement_service

CMD ["uvicorn", "services.achievement_service.main:app", "--host", "0.0.0.0", "--port", "8006"]

