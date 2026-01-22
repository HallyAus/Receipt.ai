# Worker Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (shared models and services)
COPY backend/ .

# Copy worker code
COPY worker/ ./worker/

# Create data directory
RUN mkdir -p /app/data/attachments

# Default command
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info"]
