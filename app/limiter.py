import hashlib
import time

from fastapi import HTTPException, Request

from app.config import get_settings
from app.jobs import get_redis


def _check_limit(key: str, limit: int, window: int = 60):
    now = int(time.time())
    bucket = now // window
    pipe = get_redis().pipeline()
    redis_key = f"{get_settings().REDIS_NAMESPACE}:rl:{key}:{bucket}"
    pipe.incr(redis_key)
    pipe.expire(redis_key, window * 2)
    count, _ = pipe.execute()
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window - now % window)},
        )


def rate_limit(request: Request, api_key: str, *, status: bool = False):
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    category = "status" if status else "work"
    _check_limit(
        f"{category}:ip:{ip}",
        settings.STATUS_RATE_LIMIT_PER_MINUTE_IP if status else settings.RATE_LIMIT_PER_MINUTE_IP,
    )
    digest = hashlib.sha256(api_key.encode()).hexdigest()
    _check_limit(
        f"{category}:key:{digest}",
        settings.STATUS_RATE_LIMIT_PER_MINUTE_KEY if status else settings.RATE_LIMIT_PER_MINUTE_KEY,
    )
