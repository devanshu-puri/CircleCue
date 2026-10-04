import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request
from app.core.errors import CircleCueError

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean up old timestamps
        self.requests[key] = [ts for ts in self.requests[key] if ts > window_start]
        
        if len(self.requests[key]) >= self.max_requests:
            raise CircleCueError(
                message="Rate limit exceeded. Please try again later.",
                code="RATE_LIMIT_EXCEEDED",
                status_code=429
            )
            
        self.requests[key].append(now)

code_lookup_limiter = RateLimiter(max_requests=10, window_seconds=60)
ai_parse_limiter = RateLimiter(max_requests=10, window_seconds=60)
