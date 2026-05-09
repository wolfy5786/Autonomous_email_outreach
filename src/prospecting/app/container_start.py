from __future__ import annotations

import os
import time

import pika
from pymongo import MongoClient


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _check_mongodb(mongodb_uri: str) -> None:
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
    finally:
        client.close()


def _check_rabbitmq(rabbitmq_url: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    connection.close()


def _wait_for_dependencies() -> None:
    rabbitmq_url = os.environ["RABBITMQ_URL"]
    mongodb_uri = os.environ["MONGODB_URI"]

    retries = int(os.getenv("STARTUP_RETRIES", "30"))
    sleep_seconds = float(os.getenv("STARTUP_SLEEP_SECONDS", "2"))

    for attempt in range(1, retries + 1):
        try:
            _check_mongodb(mongodb_uri)
            _check_rabbitmq(rabbitmq_url)
            print("Dependencies are reachable (MongoDB and RabbitMQ).")
            return
        except Exception as exc:
            if attempt == retries:
                raise RuntimeError(
                    f"Failed dependency check after {retries} attempts. "
                    f"MongoDB URI={mongodb_uri}, RabbitMQ URL={rabbitmq_url}"
                ) from exc

            print(
                f"Dependency check failed (attempt {attempt}/{retries}). "
                f"Retrying in {sleep_seconds}s..."
            )
            time.sleep(sleep_seconds)


def main() -> None:
    print("========================================")
    print("Prospecting Service - Container Startup")
    print("========================================")

    os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
    os.environ.setdefault("RABBITMQ_EXCHANGE", "email_outreach.events")
    os.environ.setdefault("RABBITMQ_PREFETCH", "10")
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
    os.environ.setdefault("MONGODB_DB", "email_outreach")
    os.environ.setdefault("DEFAULT_MIN_ICP_SCORE", "0.0")

    wait_for_deps = _as_bool(os.getenv("WAIT_FOR_DEPS", "true"))
    if wait_for_deps:
        _wait_for_dependencies()
    else:
        print("Skipping dependency checks because WAIT_FOR_DEPS is disabled.")

    print("Starting prospecting service...")
    from app.main import main as start_app

    start_app()


if __name__ == "__main__":
    main()
