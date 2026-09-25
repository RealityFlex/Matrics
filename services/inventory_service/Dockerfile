FROM python:3.11-slim

WORKDIR /app

COPY services/inventory_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared
COPY services/inventory_service /app/services/inventory_service

CMD ["uvicorn", "services.inventory_service.main:app", "--host", "0.0.0.0", "--port", "8005"]

