# HydroSentinel API — build context is the repository root:
#   docker build -f backend/Dockerfile -t hydrosentinel-api .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY backend/hydrosentinel backend/hydrosentinel
COPY models models
COPY data/processed data/processed

WORKDIR /app/backend
ENV HS_MODELS_DIR=/app/models HS_DATA_DIR=/app/data/processed PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
