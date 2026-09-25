FROM python:3.11-slim

WORKDIR /app

COPY services/event_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/event_service /app/services/event_service

CMD ["uvicorn", "services.event_service.main:app", "--host", "0.0.0.0", "--port", "8008"]

