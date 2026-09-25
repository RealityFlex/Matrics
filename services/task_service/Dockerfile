FROM python:3.11-slim

WORKDIR /app

COPY services/task_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/task_service /app/services/task_service

CMD ["uvicorn", "services.task_service.main:app", "--host", "0.0.0.0", "--port", "8003"]

