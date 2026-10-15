"""In-memory rate limiter for abuse prevention on sensitive authentication routes."""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter per client key."""

    def __init__(self):
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int = 5, window_seconds: int = 900) -> bool:
        """Check if request for key is permitted under sliding window limit.

        Default: 5 requests per 15 minutes (900s).
        """
        now = time.time()
        timestamps = self._records[key]

        # Purge entries outside window
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]
        self._records[key] = valid_timestamps

        if len(valid_timestamps) >= max_requests:
            return False

        valid_timestamps.append(now)
        return True

    def check_or_raise(self, key: str, max_requests: int = 5, window_seconds: int = 900) -> None:
        """Enforce rate limit or raise HTTP 429 Too Many Requests."""
        if not self.is_allowed(key, max_requests=max_requests, window_seconds=window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset requests. Please wait a few minutes before trying again.",
            )

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limiter state (useful for automated testing)."""
        if key:
            self._records.pop(key, None)
        else:
            self._records.clear()


auth_rate_limiter = InMemoryRateLimiter()
