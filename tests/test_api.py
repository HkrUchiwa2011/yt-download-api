import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from rq import SimpleWorker
from rq.serializers import JSONSerializer

from app.cleanup import cleanup_old_files
from app.jobs import (
    admitted_count,
    enqueue_download,
    get_job,
    get_queue,
    get_redis,
    set_job,
    state_key,
)
from app.models import DownloadRequest
from app.storage import job_directory
from app.tasks import format_options

URL = "https://youtu.be/BaW_jenozKc"


def test_missing_and_invalid_auth(client):
    identifier = str(uuid4())
    assert client.get(f"/status/{identifier}").status_code == 401
    assert client.get(f"/status/{identifier}", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_info_url_validated_before_extraction(client, headers, monkeypatch):
    def forbidden(*args):
        pytest.fail("Invalid input must never reach the extractor")

    monkeypatch.setattr("app.main.get_video_info", forbidden)
    assert (
        client.get(
            "/info", params={"url": "http://127.0.0.1/internal"}, headers=headers
        ).status_code
        == 422
    )


def test_validation_does_not_echo_credentials(client, headers):
    response = client.post(
        "/download",
        json={"url": URL, "webhook_url": "https://secret:password@example.org/"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "password" not in response.text
    assert "secret:" not in response.text


def test_request_body_bounded(client, headers):
    assert client.post("/download", content=b"x" * 20000, headers=headers).status_code == 413


def test_pending_job_persisted_before_response(client, headers, redisdb):
    response = client.post("/download", json={"url": URL}, headers=headers)
    assert response.status_code == 200, response.text
    identifier = response.json()["job_id"]
    assert client.get(f"/status/{identifier}", headers=headers).json()["status"] == "pending"
    assert get_queue().job_ids == [identifier]
    assert get_job(identifier)["status"] == "pending"
    assert redisdb.ttl(state_key(identifier)) > 0
    job = get_queue().fetch_job(identifier)
    assert job.serializer is JSONSerializer
    assert job.kwargs["url"] == "https://www.youtube.com/watch?v=BaW_jenozKc"


def test_global_capacity_atomic_under_concurrency(client, headers, settings):
    settings.RATE_LIMIT_PER_MINUTE_IP = settings.RATE_LIMIT_PER_MINUTE_KEY = 10000
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(
            pool.map(
                lambda _: client.post("/download", json={"url": URL}, headers=headers), range(20)
            )
        )
    assert sum(response.status_code == 200 for response in responses) == 2
    assert sum(response.status_code == 503 for response in responses) == 18
    assert admitted_count() == 2
    assert get_queue().count == 2


def test_status_has_independent_rate_budget(client, headers):
    identifier = client.post("/download", json={"url": URL}, headers=headers).json()["job_id"]
    for _ in range(15):
        assert client.get(f"/status/{identifier}", headers=headers).status_code == 200


def completed_job(settings, contents=b"media"):
    identifier = str(uuid4())
    directory = job_directory(identifier)
    directory.mkdir(parents=True)
    output = directory / "output.mp4"
    output.write_bytes(contents)
    set_job(identifier, {"status": "success", "filename": "output.mp4", "filesize": len(contents)})
    return identifier, output


def test_fetch_keeps_file_until_expiry(client, headers, settings):
    identifier, output = completed_job(settings)
    for _ in range(2):
        response = client.get(f"/file/{identifier}", headers=headers)
        assert response.content == b"media"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
    assert output.exists()
    assert client.delete(f"/file/{identifier}", headers=headers).status_code == 200
    assert not output.exists()
    assert client.get(f"/file/{identifier}", headers=headers).status_code == 404


def test_prefix_cannot_delete_file(client, headers, settings):
    identifier, output = completed_job(settings)
    assert client.delete(f"/file/{identifier[:8]}", headers=headers).status_code == 422
    assert output.exists()


def test_output_symlink_not_served(client, headers, settings, tmp_path):
    identifier, output = completed_job(settings)
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    output.unlink()
    output.symlink_to(secret)
    assert client.get(f"/file/{identifier}", headers=headers).status_code == 404
    assert secret.read_text() == "private"


def test_cleanup_preserves_active_jobs_and_removes_expired(redisdb, settings):
    identifier = enqueue_download(DownloadRequest(url=URL))
    directory = job_directory(identifier)
    directory.mkdir(parents=True)
    (directory / "output.mp4.part").write_bytes(b"partial")
    old = time.time() - 10000
    os.utime(directory, (old, old))
    cleanup_old_files()
    assert directory.exists()
    redisdb.delete(state_key(identifier))
    cleanup_old_files()
    assert not directory.exists()


def test_health_detects_missing_workers(client):
    assert client.get("/health").status_code == 503


def test_active_job_cannot_be_deleted(client, headers):
    identifier = client.post("/download", json={"url": URL}, headers=headers).json()["job_id"]
    assert client.delete(f"/file/{identifier}", headers=headers).status_code == 409


@pytest.mark.parametrize("format", ["mp4", "mp3", "webm"])
def test_formats_select_appropriate_streams(format):
    opts = format_options(format, "720p")
    if format == "mp3":
        assert opts["format"] == "bestaudio/best"
    else:
        assert f"ext={format}" in opts["format"]
        assert "height<=720" in opts["format"]
        assert opts["merge_output_format"] == format


class FakeYDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def extract_info(self, url, download=False):
        return {"title": "Fixture", "duration": 10, "formats": []}

    def process_ie_result(self, info, download):
        from pathlib import Path

        extension = (
            "mp3" if "postprocessors" in self.options else self.options["merge_output_format"]
        )
        output = Path(self.options["outtmpl"].replace("%(ext)s", extension))
        output.write_bytes(b"fixture")
        for hook in self.options["progress_hooks"]:
            hook({"status": "finished"})


@pytest.mark.parametrize("format", ["mp4", "mp3", "webm"])
def test_pending_jobs_survive_api_connection_restart_and_run(
    redisdb, settings, monkeypatch, format
):
    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", FakeYDL)
    identifier = enqueue_download(DownloadRequest(url=URL, format=format))
    get_redis.cache_clear()
    worker = SimpleWorker(
        [get_queue()],
        connection=get_redis(),
        serializer=JSONSerializer,
        name=settings.REDIS_NAMESPACE + "-worker",
    )
    worker.work(burst=True, logging_level="WARNING")
    assert get_job(identifier)["status"] == "success"
    assert get_job(identifier)["filename"] == f"output.{format}"
    assert admitted_count() == 0


def test_failure_releases_capacity_and_removes_partials(redisdb, settings, monkeypatch):
    class TooLong(FakeYDL):
        def extract_info(self, *args, **kwargs):
            return {"title": "Fixture", "duration": 999999}

    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", TooLong)
    identifier = enqueue_download(DownloadRequest(url=URL))
    SimpleWorker(
        [get_queue()],
        connection=redisdb,
        serializer=JSONSerializer,
        name=settings.REDIS_NAMESPACE + "-worker",
    ).work(burst=True, logging_level="WARNING")
    assert get_job(identifier)["status"] == "failure"
    assert "duration limit" in get_job(identifier)["error"]
    assert admitted_count() == 0
    assert not job_directory(identifier).exists()


def test_no_api_secret_in_redis_key_names(client, headers, redisdb):
    client.post("/download", json={"url": URL}, headers=headers)
    assert all(headers["X-API-Key"] not in key.decode() for key in redisdb.scan_iter())


def test_metadata_success_releases_global_slot(client, headers, settings, monkeypatch, redisdb):
    monkeypatch.setattr(
        "app.main.get_video_info", lambda url: {"title": "Fixture", "duration": None, "formats": []}
    )
    response = client.get("/info", params={"url": URL}, headers=headers)
    assert response.status_code == 200
    assert response.json()["duration"] is None
    assert redisdb.zcard(settings.REDIS_NAMESPACE + ":info") == 0


def test_metadata_failure_releases_global_slot(client, headers, settings, monkeypatch, redisdb):
    def fail(url):
        raise ValueError("upstream credentials must not be echoed")

    monkeypatch.setattr("app.main.get_video_info", fail)
    response = client.get("/info", params={"url": URL}, headers=headers)
    assert response.status_code == 400
    assert "credentials" not in response.text
    assert redisdb.zcard(settings.REDIS_NAMESPACE + ":info") == 0


def test_storage_reservations_are_atomic(client, headers, settings, monkeypatch):
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(
        "app.jobs.shutil.disk_usage", lambda path: usage(10 * 1024**2, 7 * 1024**2, 3 * 1024**2)
    )
    assert client.post("/download", json={"url": URL}, headers=headers).status_code == 200
    assert client.post("/download", json={"url": URL}, headers=headers).status_code == 503
    assert admitted_count() == 1


def test_bad_auth_has_a_rate_limit(client, headers):
    identifier = str(uuid4())
    responses = [
        client.get(f"/status/{identifier}", headers={"X-API-Key": "wrong"}) for _ in range(61)
    ]
    assert responses[-1].status_code == 429
    assert "Retry-After" in responses[-1].headers


def test_redis_outage_returns_sanitized_503(client, headers, monkeypatch):
    from redis.exceptions import ConnectionError

    def unavailable(*args):
        raise ConnectionError("redis://user:secret@host")

    monkeypatch.setattr("app.limiter._check_limit", unavailable)
    response = client.get(f"/status/{uuid4()}", headers=headers)
    assert response.status_code == 503
    assert "secret" not in response.text


def test_rq_failure_marks_job_and_releases_slot(redisdb, settings):
    identifier = enqueue_download(DownloadRequest(url=URL))
    job = get_queue().fetch_job(identifier)
    job.set_status("failed")
    assert get_job(identifier)["status"] == "failure"
    assert admitted_count() == 0


def blocking_info_child(connection, url):
    time.sleep(10)


def test_metadata_process_has_a_hard_deadline(settings, monkeypatch):
    from app.tasks import get_video_info

    settings.SOCKET_TIMEOUT_SECONDS = 1
    monkeypatch.setattr("app.tasks._info_child", blocking_info_child)
    started = time.monotonic()
    with pytest.raises(ValueError, match="timed out"):
        get_video_info(URL)
    assert time.monotonic() - started < 6


def test_late_worker_failure_preserves_completed_file(redisdb, settings):
    from app.jobs import fail_job

    identifier = enqueue_download(DownloadRequest(url=URL))
    directory = job_directory(identifier)
    directory.mkdir(parents=True)
    output = directory / "output.mp4"
    output.write_bytes(b"completed")
    set_job(identifier, {"status": "success", "filename": "output.mp4"})
    fail_job(get_queue().fetch_job(identifier), redisdb, None, None, None)
    assert get_job(identifier)["status"] == "success"
    assert output.read_bytes() == b"completed"
    assert admitted_count() == 0


@pytest.mark.parametrize(
    "byte_range,expected", [("bytes=1-3", b"edi"), ("bytes=-3", b"dia"), ("bytes=2-", b"dia")]
)
def test_file_byte_ranges(client, headers, settings, byte_range, expected):
    identifier, _ = completed_job(settings)
    response = client.get(f"/file/{identifier}", headers={**headers, "Range": byte_range})
    assert response.status_code == 206
    assert response.content == expected
    assert response.headers["Content-Length"] == str(len(expected))
    assert response.headers["Accept-Ranges"] == "bytes"


def test_invalid_range_and_if_range(client, headers, settings):
    identifier, _ = completed_job(settings)
    assert (
        client.get(f"/file/{identifier}", headers={**headers, "Range": "bytes=100-200"}).status_code
        == 416
    )
    response = client.get(
        f"/file/{identifier}", headers={**headers, "Range": "bytes=1-2", "If-Range": '"old"'}
    )
    assert response.status_code == 200
    assert response.content == b"media"


def test_worker_timeout_releases_capacity(redisdb, settings, monkeypatch):
    from rq import Worker

    class SlowYDL(FakeYDL):
        def extract_info(self, *args, **kwargs):
            time.sleep(30)
            return super().extract_info(*args, **kwargs)

    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", SlowYDL)
    identifier = enqueue_download(DownloadRequest(url=URL))
    started = time.monotonic()
    Worker(
        [get_queue()],
        connection=redisdb,
        serializer=JSONSerializer,
        name=settings.REDIS_NAMESPACE + "-worker",
    ).work(burst=True, logging_level="WARNING")
    assert time.monotonic() - started < 20
    assert get_job(identifier)["status"] == "failure"
    assert get_job(identifier)["error"] == "Download timed out"
    assert admitted_count() == 0
    assert not job_directory(identifier).exists()
