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

# sentence-transformers (used for dense retrieval embeddings, Milestone 6)
# pulls in torch as a transitive dependency. Installing plain "torch" here
# would pull the full CUDA runtime wheels (nvidia-cublas, nvidia-cusparselt,
# etc.) even though this container only ever runs on CPU - that mistake was
# made and fixed in Milestone 1 (see clauseguard_build_conventions memory).
# Installing the CPU-only wheel first means the main install below is
# satisfied by it instead of pulling a CUDA build.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install only the runtime dependency set (no training extras: LoRA
# fine-tuning stays a separate local environment, not the served app).
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
