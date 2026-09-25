FROM python:3.11-slim

WORKDIR /app

COPY services/competition_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/task_service /app/services/task_service
COPY services/competition_service /app/services/competition_service

CMD ["uvicorn", "services.competition_service.main:app", "--host", "0.0.0.0", "--port", "8010"]

