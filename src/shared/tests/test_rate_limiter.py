"""Unit tests for the token-bucket rate limiter."""
import asyncio
import pytest
import time
from src.shared.observability.rate_limiter import TokenBucket


def test_try_acquire_success():
    bucket = TokenBucket(rate=10.0, capacity=10.0)
    assert bucket.try_acquire(1.0) is True


def test_try_acquire_exhausted():
    bucket = TokenBucket(rate=1.0, capacity=2.0)
    assert bucket.try_acquire(2.0) is True
    assert bucket.try_acquire(1.0) is False


def test_try_acquire_refills():
    bucket = TokenBucket(rate=100.0, capacity=5.0)
    bucket.try_acquire(5.0)
    time.sleep(0.05)  # refill ~5 tokens at 100/s
    assert bucket.try_acquire(1.0) is True


@pytest.mark.asyncio
async def test_acquire_waits():
    bucket = TokenBucket(rate=100.0, capacity=1.0)
    bucket.try_acquire(1.0)  # exhaust
    start = time.monotonic()
    await bucket.acquire(1.0)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005  # should have waited
