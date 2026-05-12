FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/sourcing \
    SERVICE_NAME=sourcing

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

# Monorepo: build context must be ./src (see docker-compose sourcing.build)
COPY sourcing/requirements.txt /app/sourcing/requirements.txt
RUN pip install --no-cache-dir -r /app/sourcing/requirements.txt

COPY shared /app/shared
COPY sourcing /app/sourcing

WORKDIR /app/sourcing

USER appuser

CMD ["python", "main.py"]
