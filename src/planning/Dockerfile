# syntax=docker/dockerfile:1.7

# ── builder ──────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install dependencies into the system site-packages — simpler than a venv inside a container.
COPY src/planning/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir \
      "aio-pika>=9.4,<10" \
      "motor>=3.5,<4" \
      "pymongo>=4.8,<5" \
      "litellm>=1.51,<2" \
      "pydantic>=2.8,<3" \
      "pydantic-settings>=2.4,<3" \
      "fastapi>=0.115,<1" \
      "uvicorn[standard]>=0.30,<1" \
      "tenacity>=9.0,<10" \
      "structlog>=24.4,<25"

# ── runtime ──────────────────────────────────────────────
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app

# Pull installed site-packages from builder.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy service code and shared broker code. Layout on disk:
#   /app/planning/...                    <- the service
#   /app/local_infrastructure/...        <- the shared broker package
COPY src/planning/planning /app/planning
COPY src/local_infrastructure /app/local_infrastructure

USER app
EXPOSE 8080
CMD ["python", "-m", "planning.main"]
