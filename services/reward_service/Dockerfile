FROM python:3.11-slim

WORKDIR /app

COPY services/reward_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/reward_service /app/services/reward_service

CMD ["uvicorn", "services.reward_service.main:app", "--host", "0.0.0.0", "--port", "8011"]

