"""Per-domain rate limiter."""
import time
import asyncio
import logging
from collections import defaultdict

log = logging.getLogger("galaxy.collection")


class RateLimiter:
    """Adaptive per-domain rate limiter."""
    
    def __init__(self, default_rate: float = 2.0):
        self._default_rate = default_rate  # req/sec
        self._domain_rates: dict[str, float] = {}
        self._last_request: dict[str, float] = defaultdict(float)
    
    def set_rate(self, domain: str, rate: float):
        self._domain_rates[domain] = rate
    
    async def acquire(self, domain: str):
        """Wait if needed to respect rate limit."""
        rate = self._domain_rates.get(domain, self._default_rate)
        min_interval = 1.0 / rate
        now = time.time()
        elapsed = now - self._last_request[domain]
        if elapsed < min_interval:
            wait = min_interval - elapsed
            log.debug(f"Rate limit: waiting {wait:.2f}s for {domain}")
            await asyncio.sleep(wait)
        self._last_request[domain] = time.time()
    
    def acquire_sync(self, domain: str):
        """Synchronous version."""
        rate = self._domain_rates.get(domain, self._default_rate)
        min_interval = 1.0 / rate
        now = time.time()
        elapsed = now - self._last_request[domain]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request[domain] = time.time()
