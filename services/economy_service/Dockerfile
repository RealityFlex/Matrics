FROM python:3.11-slim

WORKDIR /app

COPY services/economy_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/economy_service /app/services/economy_service

CMD ["uvicorn", "services.economy_service.main:app", "--host", "0.0.0.0", "--port", "8009"]

