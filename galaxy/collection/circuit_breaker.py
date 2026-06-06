"""Per-source circuit breaker."""
import time
import logging
from enum import Enum

log = logging.getLogger("galaxy.collection")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-source circuit breaker to prevent cascading failures."""
    
    def __init__(self, failure_threshold: int = 5, open_duration: float = 60.0, half_open_max: int = 3):
        self._circuits: dict[str, dict] = {}
        self._failure_threshold = failure_threshold
        self._open_duration = open_duration
        self._half_open_max = half_open_max
    
    def _get(self, source: str) -> dict:
        if source not in self._circuits:
            self._circuits[source] = {
                "state": CircuitState.CLOSED,
                "failures": 0, "successes": 0,
                "opened_at": 0, "duration": self._open_duration,
                "half_open_attempts": 0,
            }
        return self._circuits[source]
    
    def can_request(self, source: str) -> bool:
        """Check if requests are allowed for this source."""
        cb = self._get(source)
        if cb["state"] == CircuitState.CLOSED:
            return True
        if cb["state"] == CircuitState.OPEN:
            if time.time() - cb["opened_at"] > cb["duration"]:
                cb["state"] = CircuitState.HALF_OPEN
                cb["half_open_attempts"] = 0
                log.info(f"Circuit half-open: {source}")
                return True
            return False
        if cb["state"] == CircuitState.HALF_OPEN:
            return cb["half_open_attempts"] < self._half_open_max
        return True
    
    def record_success(self, source: str):
        cb = self._get(source)
        cb["successes"] += 1
        if cb["state"] == CircuitState.HALF_OPEN:
            cb["half_open_attempts"] += 1
            if cb["half_open_attempts"] >= self._half_open_max:
                cb["state"] = CircuitState.CLOSED
                cb["failures"] = 0
                log.info(f"Circuit closed: {source}")
    
    def record_failure(self, source: str):
        cb = self._get(source)
        cb["failures"] += 1
        if cb["state"] == CircuitState.HALF_OPEN:
            cb["state"] = CircuitState.OPEN
            cb["opened_at"] = time.time()
            cb["duration"] *= 2
            log.warning(f"Circuit re-opened: {source} (duration={cb['duration']}s)")
        elif cb["failures"] >= self._failure_threshold:
            cb["state"] = CircuitState.OPEN
            cb["opened_at"] = time.time()
            log.warning(f"Circuit opened: {source} after {cb['failures']} failures")
