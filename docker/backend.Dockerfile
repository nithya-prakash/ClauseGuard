FROM python:3.12-slim AS base

# Native deps: libpq for psycopg, build tools for any source wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY backend ./backend

# Install only the runtime dependency set (no training extras: keeps the
# backend/worker image free of torch/transformers, which belong to the
# separate local LoRA training environment, not the served application).
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
