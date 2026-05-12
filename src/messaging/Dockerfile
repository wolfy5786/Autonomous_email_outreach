FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

# Monorepo: build context must be ./src (see docker-compose messaging.build).
COPY messaging/pyproject.toml /tmp/pyproject.toml
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
      "structlog>=24.4,<25" \
      "beanie>=1.26,<2" \
      "google-auth>=2.34,<3" \
      "google-auth-oauthlib>=1.2,<2" \
      "google-api-python-client>=2.140,<3"

COPY shared /app/shared
COPY local_infrastructure /app/local_infrastructure
COPY messaging/messaging /app/messaging

USER appuser

EXPOSE 8081

CMD ["python", "-m", "messaging.main"]
