FROM python:3.11-slim

WORKDIR /app

COPY services/statistics_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/statistics_service /app/services/statistics_service

CMD ["uvicorn", "services.statistics_service.main:app", "--host", "0.0.0.0", "--port", "8012"]

