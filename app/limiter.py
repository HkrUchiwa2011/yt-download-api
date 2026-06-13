import time
import redis as redis_client
from fastapi import HTTPException, Request
from app.config import get_settings

settings = get_settings()


def _get_redis():
    return redis_client.from_url(settings.REDIS_URL, decode_responses=True)


def _check_limit(key: str, limit: int, window: int = 60):
    r = _get_redis()
    pipe = r.pipeline()
    now = int(time.time())
    bucket = now // window

    redis_key = f"rl:{key}:{bucket}"
    pipe.incr(redis_key)
    pipe.expire(redis_key, window * 2)
    count, _ = pipe.execute()

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {limit} requests per minute.",
            headers={"Retry-After": str(window - (now % window))},
        )


def rate_limit(request: Request, api_key: str | None = None):
    ip = request.client.host if request.client else "unknown"
    _check_limit(f"ip:{ip}", settings.RATE_LIMIT_PER_MINUTE_IP)

    if api_key:
        _check_limit(f"key:{api_key}", settings.RATE_LIMIT_PER_MINUTE_KEY)
