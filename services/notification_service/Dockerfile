FROM python:3.11-slim

WORKDIR /app

COPY services/notification_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/notification_service /app/services/notification_service

CMD ["uvicorn", "services.notification_service.main:app", "--host", "0.0.0.0", "--port", "8013"]


