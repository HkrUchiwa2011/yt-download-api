"""Redis admission and RQ jobs use JSON, never executable pickle payloads."""

import json
import shutil
from functools import lru_cache
from uuid import uuid4

import redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Callback, Job
from rq.serializers import JSONSerializer

from app.config import get_settings

ACTIVE = {"pending", "started", "progress", "post_processing"}
ADMIT = """
local now = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[1]) then return 0 end
if tonumber(ARGV[4]) < (count + 1) * tonumber(ARGV[5]) + tonumber(ARGV[6]) then return -1 end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
return 1
"""


@lru_cache
def get_redis():
    return redis.Redis.from_url(
        get_settings().REDIS_URL.get_secret_value(),
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=30,
    )


def get_queue():
    return Queue(
        get_settings().REDIS_NAMESPACE + "-downloads",
        connection=get_redis(),
        serializer=JSONSerializer,
    )


def state_key(job_id: str):
    return f"{get_settings().REDIS_NAMESPACE}:job:{job_id}"


def set_job(job_id: str, data: dict):
    settings = get_settings()
    ttl = (
        settings.FILE_TTL_MINUTES * 60
        if data["status"] not in ACTIVE
        else settings.JOB_TIMEOUT_SECONDS * 2 + 120
    )
    get_redis().set(
        state_key(job_id), json.dumps({**data, "expires_at": get_redis().time()[0] + ttl}), ex=ttl
    )


def slots_key():
    return get_settings().REDIS_NAMESPACE + ":admitted"


def release_slot(job_id: str):
    get_redis().zrem(slots_key(), job_id)


def fail_job(job, connection, exc_type, exc_value, traceback):
    from app.storage import remove_job_files

    raw = get_redis().get(state_key(job.id))
    if raw and json.loads(raw)["status"] not in ACTIVE:
        # A callback timeout or crash after completion must not delete a valid file.
        release_slot(job.id)
        return
    set_job(
        job.id,
        {"status": "failure", "error": "Download interrupted or timed out. Submit a new job."},
    )
    release_slot(job.id)
    remove_job_files(job.id)
    if job.kwargs.get("webhook_url"):
        from app.security import notify_webhook

        notify_webhook(
            job.kwargs["webhook_url"],
            {"job_id": job.id, "status": "failure", "error": "Download interrupted or timed out"},
        )


def get_job(job_id: str) -> dict | None:
    raw = get_redis().get(state_key(job_id))
    if not raw:
        return None
    data = json.loads(raw)
    if data["status"] in ACTIVE:
        try:
            job = Job.fetch(job_id, connection=get_redis(), serializer=JSONSerializer)
            if job.get_status(refresh=True) in {"failed", "stopped", "canceled"}:
                fail_job(job, get_redis(), None, None, None)
                return json.loads(get_redis().get(state_key(job_id)))
        except NoSuchJobError:
            set_job(
                job_id,
                {"status": "failure", "error": "Job expired before completion. Submit a new job."},
            )
            release_slot(job_id)
            return json.loads(get_redis().get(state_key(job_id)))
    return data


def enqueue_download(body) -> str:
    settings = get_settings()
    job_id = str(uuid4())
    ttl = settings.JOB_TIMEOUT_SECONDS * 2 + 120
    from app.storage import ensure_storage

    ensure_storage()
    admitted = get_redis().eval(
        ADMIT,
        1,
        slots_key(),
        settings.MAX_CONCURRENT_DOWNLOADS,
        ttl,
        job_id,
        shutil.disk_usage(settings.TMP_DIR).free,
        settings.MAX_FILESIZE_MB * 2 * 1024**2,
        settings.MIN_FREE_SPACE_MB * 1024**2,
    )
    if admitted == 0:
        raise OverflowError("Download capacity reached")
    if admitted == -1:
        raise ValueError("Insufficient free storage")
    expires_at = get_redis().time()[0] + ttl
    try:
        # Commit initial state and queue entry together: immediate polling is safe.
        with get_redis().pipeline() as pipe:
            job = get_queue().create_job(
                "app.tasks.run_download",
                kwargs={
                    "job_id": job_id,
                    "url": body.url,
                    "format": body.format.value,
                    "quality": body.quality.value,
                    "webhook_url": body.webhook_url,
                },
                job_id=job_id,
                timeout=settings.JOB_TIMEOUT_SECONDS,
                ttl=settings.JOB_TIMEOUT_SECONDS,
                result_ttl=settings.FILE_TTL_MINUTES * 60,
                failure_ttl=settings.FILE_TTL_MINUTES * 60,
                on_failure=Callback(fail_job, timeout=30),
                description=f"Download {job_id}",
            )
            get_queue().enqueue_job(job, pipeline=pipe)
            pipe.set(
                state_key(job_id),
                json.dumps({"status": "pending", "expires_at": expires_at}),
                ex=ttl,
            )
            pipe.execute()
    except Exception:
        release_slot(job_id)
        raise
    return job_id


def admitted_count():
    r = get_redis()
    r.zremrangebyscore(slots_key(), "-inf", r.time()[0])
    return r.zcard(slots_key())
