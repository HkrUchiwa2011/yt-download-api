import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEY", "test" * 8)

from app.config import get_settings  # noqa: E402
from app.jobs import get_queue, get_redis  # noqa: E402


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEY", "test" * 8)
    monkeypatch.setenv("TMP_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("REDIS_NAMESPACE", "test-" + uuid4().hex)
    monkeypatch.setenv("REDIS_URL", os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:16379/15"))
    monkeypatch.setenv("MAX_FILESIZE_MB", "1")
    monkeypatch.setenv("MIN_FREE_SPACE_MB", "0")
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("MAX_CONCURRENT_DOWNLOADS", "2")
    get_settings.cache_clear()
    get_redis.cache_clear()
    yield get_settings()
    get_redis.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def redisdb(settings):
    if not os.getenv("TEST_REDIS_URL"):
        pytest.skip("Set TEST_REDIS_URL to an isolated test Redis")
    r = get_redis()
    r.ping()
    yield r
    # Remove only this test's namespaced keys and its own RQ job records.
    state_keys = list(r.scan_iter(settings.REDIS_NAMESPACE + ":job:*"))
    for key in state_keys:
        identifier = key.decode().rsplit(":", 1)[1]
        r.delete("rq:job:" + identifier, "rq:results:" + identifier)
    keys = list(r.scan_iter(settings.REDIS_NAMESPACE + ":*"))
    keys += list(r.scan_iter("rq:*" + settings.REDIS_NAMESPACE + "*"))
    if keys:
        r.delete(*keys)
    r.srem("rq:queues", get_queue().key)


@pytest.fixture
def client(redisdb):
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers():
    return {"X-API-Key": "test" * 8}
