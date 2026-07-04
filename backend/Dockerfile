# =============================================================================
# Stage 1: Builder - installs build dependencies and compiles Python wheels
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time OS deps needed to compile psycopg2-binary and friends.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels so the final stage does not need a compiler at all.
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# =============================================================================
# Stage 2: Runtime - minimal, non-root, no build tools
# =============================================================================
FROM python:3.12-slim AS runtime

LABEL maintainer="devsecops-mothership" \
      description="Secure Task & Asset Manager - Backend API"

# Runtime-only OS dependency (libpq5) required by psycopg2 at import time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appgroup \
    && useradd --system --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /build/wheels /wheels
COPY requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels requirements.txt

COPY --chown=appuser:appgroup main.py database.py models.py schemas.py ./

# Writable directory for any runtime tmp needs since the root FS is read-only
# at the Kubernetes SecurityContext level (readOnlyRootFilesystem: true).
RUN mkdir -p /app/tmp && chown -R appuser:appgroup /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
