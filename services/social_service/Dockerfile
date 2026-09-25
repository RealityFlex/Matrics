FROM python:3.11-slim

WORKDIR /app

COPY services/social_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/social_service /app/services/social_service

CMD ["uvicorn", "services.social_service.main:app", "--host", "0.0.0.0", "--port", "8007"]

