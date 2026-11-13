import hashlib
import hmac
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from email.utils import formatdate
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from redis.exceptions import RedisError
from rq import Worker

from app.cleanup import cleanup_old_files
from app.config import get_settings
from app.jobs import ADMIT, admitted_count, enqueue_download, get_job, get_queue, get_redis, set_job
from app.limiter import _check_limit, rate_limit
from app.middleware import BodyLimitMiddleware
from app.models import DownloadRequest, DownloadResponse, StatusResponse, VideoInfo
from app.security import youtube_url
from app.storage import check_free_space, ensure_storage, open_output, remove_job_files
from app.tasks import get_video_info

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage()
    stop = threading.Event()

    def cleanup_loop():
        while not stop.wait(60):
            try:
                cleanup_old_files()
            except (RedisError, OSError, ValueError):
                logger.warning("File cleanup temporarily unavailable")

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=6)


class OpenFileResponse(StreamingResponse):
    def __init__(self, file, *args, **kwargs):
        self.file = file
        super().__init__(*args, **kwargs)

    async def __call__(self, *args, **kwargs):
        try:
            await super().__call__(*args, **kwargs)
        finally:
            self.file.close()


app = FastAPI(
    title="yt-download-api",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().ENABLE_DOCS else None,
    openapi_url="/openapi.json" if get_settings().ENABLE_DOCS else None,
    redoc_url=None,
)


app.add_middleware(BodyLimitMiddleware)


@app.exception_handler(RedisError)
async def redis_unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Storage temporarily unavailable"},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Pydantic includes rejected input by default, which can disclose URL credentials.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def get_api_key(
    request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> str:
    secret = get_settings().API_KEY.get_secret_value()
    if not x_api_key or not hmac.compare_digest(
        hashlib.sha256(x_api_key.encode()).digest(), hashlib.sha256(secret.encode()).digest()
    ):
        _check_limit(f"auth:ip:{request.client.host if request.client else 'unknown'}", 60)
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@app.get("/health", tags=["System"])
def health(request: Request):
    _check_limit(f"health:ip:{request.client.host if request.client else 'unknown'}", 120)
    get_redis().ping()
    workers = Worker.all(queue=get_queue())
    if not workers:
        raise HTTPException(
            status_code=503, detail="No download worker available", headers={"Retry-After": "5"}
        )
    return {"status": "ok", "version": app.version, "active_downloads": admitted_count()}


@app.get("/info", response_model=VideoInfo, tags=["Video"])
def video_info(
    request: Request, url: str = Query(max_length=2048), api_key: str = Depends(get_api_key)
):
    rate_limit(request, api_key)
    try:
        canonical = youtube_url(url)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid YouTube URL") from None
    settings = get_settings()
    slot = str(uuid4())
    key = settings.REDIS_NAMESPACE + ":info"
    if (
        get_redis().eval(
            ADMIT,
            1,
            key,
            settings.MAX_CONCURRENT_INFO_REQUESTS,
            settings.SOCKET_TIMEOUT_SECONDS * 3 + 10,
            slot,
            2**60,
            0,
            0,
        )
        != 1
    ):
        raise HTTPException(
            status_code=503, detail="Metadata capacity reached", headers={"Retry-After": "5"}
        )
    try:
        return get_video_info(canonical)
    except ValueError:
        raise HTTPException(status_code=400, detail="Video metadata unavailable") from None
    finally:
        get_redis().zrem(key, slot)


@app.post("/download", response_model=DownloadResponse, tags=["Video"])
def submit_download(body: DownloadRequest, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)
    try:
        check_free_space()
    except ValueError:
        raise HTTPException(
            status_code=503, detail="Insufficient free storage", headers={"Retry-After": "60"}
        ) from None
    try:
        job_id = enqueue_download(body)
    except ValueError:
        raise HTTPException(
            status_code=503, detail="Insufficient free storage", headers={"Retry-After": "60"}
        ) from None
    except OverflowError:
        raise HTTPException(
            status_code=503, detail="Download capacity reached", headers={"Retry-After": "5"}
        ) from None
    return DownloadResponse(
        job_id=job_id, status="pending", message=f"Job queued. Poll status at GET /status/{job_id}"
    )


@app.get("/status/{job_id}", response_model=StatusResponse, tags=["Video"])
def get_status(job_id: UUID, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key, status=True)
    identifier = str(job_id)
    job = get_job(identifier)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    state = job["status"]
    progress = None
    if state == "success":
        progress = {key: job.get(key) for key in ("title", "duration", "filesize")}
    elif state in {"progress", "post_processing"}:
        progress = job.get("progress", {})
    return StatusResponse(
        job_id=identifier,
        status=state,
        progress=progress,
        error=job.get("error"),
        download_url=f"/file/{identifier}" if state == "success" else None,
    )


@app.get("/file/{job_id}", tags=["Video"])
def download_file(job_id: UUID, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)
    identifier = str(job_id)
    job = get_job(identifier)
    if not job or job["status"] != "success":
        raise HTTPException(status_code=404, detail="File not available or expired")
    try:
        file = open_output(identifier, job.get("filename", ""))
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="File not available or expired") from None
    stat = os.fstat(file.fileno())
    size = stat.st_size
    etag = '"' + hashlib.sha256(f"{stat.st_mtime_ns}:{size}".encode()).hexdigest() + '"'
    modified = formatdate(stat.st_mtime, usegmt=True)
    start, end, status_code = 0, size - 1, 200
    requested = request.headers.get("Range")
    if_range = request.headers.get("If-Range")
    if requested and (not if_range or if_range in {etag, modified}):
        match = (
            re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", requested) if len(requested) <= 128 else None
        )
        try:
            if not match or not any(match.groups()):
                raise ValueError
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                suffix = int(last)
                if suffix <= 0:
                    raise ValueError
                start = max(0, size - suffix)
            if start > end or start >= size:
                raise ValueError
            status_code = 206
        except ValueError:
            file.close()
            raise HTTPException(
                status_code=416,
                detail="Unsatisfiable byte range",
                headers={"Content-Range": f"bytes */{size}"},
            ) from None
    file.seek(start)
    length = max(0, end - start + 1)

    def chunks():
        remaining = length
        try:
            while remaining:
                chunk = file.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            file.close()

    headers = {
        "Content-Disposition": f'attachment; filename="{identifier}.{job["filename"].split(".")[-1]}"',
        "Content-Length": str(length),
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Last-Modified": modified,
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return OpenFileResponse(
        file,
        chunks(),
        media_type="application/octet-stream",
        headers=headers,
        status_code=status_code,
    )


@app.delete("/file/{job_id}", tags=["Video"])
def delete_file(job_id: UUID, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)
    identifier = str(job_id)
    job = get_job(identifier)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    if job["status"] not in {"success", "failure"}:
        raise HTTPException(status_code=409, detail="Download is still active")
    remove_job_files(identifier)
    set_job(identifier, {"status": "failure", "error": "File deleted"})
    return {"message": "File deleted"}
