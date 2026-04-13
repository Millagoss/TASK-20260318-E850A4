FROM python:3.11-slim

WORKDIR /app

# Ensure local volume directory exists
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/uploads /app/backups /app/scripts

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/scripts/daily_backup.sh

# Tables are created via SQLAlchemy create_all on app import (see README); start API.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
