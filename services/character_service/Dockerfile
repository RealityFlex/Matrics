FROM python:3.11-slim

WORKDIR /app

COPY services/character_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/character_service /app/services/character_service

CMD ["uvicorn", "services.character_service.main:app", "--host", "0.0.0.0", "--port", "8002"]

