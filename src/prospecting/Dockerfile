FROM python:3.11-slim

# Build context is ./src so we can pull in the shared/ package for
# shared.observability.configure_logging — see docker-compose.yml.

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY prospecting/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Service code, tests, and the shared package (for structured logging).
COPY prospecting/app /app/app
COPY prospecting/tests /app/tests
COPY shared /app/shared

EXPOSE 8004

CMD ["python", "-m", "app.container_start"]
