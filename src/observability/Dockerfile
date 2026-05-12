FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=observability

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

# Monorepo: build context must be ./src (see docker-compose observability.build).
COPY observability/pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir \
      "motor>=3.5,<4" \
      "pymongo>=4.8,<5" \
      "pydantic>=2.8,<3" \
      "pydantic-settings>=2.4,<3" \
      "fastapi>=0.115,<1" \
      "uvicorn[standard]>=0.30,<1" \
      "jinja2>=3.1,<4" \
      "structlog>=24.4,<25" \
      "beanie>=1.26,<2"

COPY shared /app/shared
COPY observability/observability /app/observability

USER appuser

EXPOSE 8090

CMD ["python", "-m", "observability.main"]
