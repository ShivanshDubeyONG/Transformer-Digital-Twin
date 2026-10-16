# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    PYTHONPATH=/app/backend

WORKDIR /app

# Install native Linux libraries for WeasyPrint, Matplotlib headless rendering, and health check curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first for efficient Docker layer caching
COPY backend/pyproject.toml /app/backend/pyproject.toml

# Install backend dependencies with dev extras
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "/app/backend[dev]"

# Copy application source and project assets
COPY backend /app/backend
COPY data /app/data
COPY fixtures /app/fixtures
COPY demo_script.py /app/demo_script.py

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
