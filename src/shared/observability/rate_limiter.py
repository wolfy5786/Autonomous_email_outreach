"""Token-bucket rate limiter for outbound API calls."""
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Simple token-bucket rate limiter."""

    rate: float          # tokens added per second
    capacity: float      # max burst size
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until the requested number of tokens is available."""
        while True:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            deficit = tokens - self._tokens
            wait = deficit / self.rate
            await asyncio.sleep(wait)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Non-blocking acquire — returns False if not enough tokens."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False
