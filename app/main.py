import os
import uuid
import threading
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, Request
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import DownloadRequest, DownloadResponse, StatusResponse, VideoInfo
from app.tasks import run_download, get_job, get_video_info, _find_output_file
from app.limiter import rate_limit
from app.cleanup import cleanup_old_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

_active_downloads: set[str] = set()
_downloads_lock = threading.Lock()


def _cleanup_scheduler():
    while True:
        time.sleep(settings.FILE_TTL_MINUTES * 60)
        cleanup_old_files()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.TMP_DIR, exist_ok=True)
    threading.Thread(target=_cleanup_scheduler, daemon=True).start()
    logger.info("API started")
    yield
    logger.info("API shutting down")


app = FastAPI(
    title="yt-download-api",
    description="Self-hostable YouTube download API built with FastAPI and yt-dlp.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)


def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def check_concurrent_limit():
    with _downloads_lock:
        if len(_active_downloads) >= settings.MAX_CONCURRENT_DOWNLOADS:
            raise HTTPException(
                status_code=503,
                detail=f"Server busy. Max {settings.MAX_CONCURRENT_DOWNLOADS} concurrent downloads.",
            )


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "version": app.version,
        "active_downloads": len(_active_downloads),
    }


@app.get("/info", response_model=VideoInfo, tags=["Video"])
def video_info(url: str, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)
    try:
        return get_video_info(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/download", response_model=DownloadResponse, tags=["Video"])
def submit_download(
    body: DownloadRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    rate_limit(request, api_key)
    check_concurrent_limit()

    job_id = str(uuid.uuid4())

    with _downloads_lock:
        _active_downloads.add(job_id)

    def run_and_cleanup(*args, **kwargs):
        try:
            run_download(*args, **kwargs)
        finally:
            with _downloads_lock:
                _active_downloads.discard(job_id)

    background_tasks.add_task(
        run_and_cleanup,
        job_id=job_id,
        url=body.url,
        format=body.format.value,
        quality=body.quality.value,
        webhook_url=body.webhook_url,
    )

    return DownloadResponse(
        job_id=job_id,
        status="pending",
        message=f"Job queued. Poll status at GET /status/{job_id}",
    )


@app.get("/status/{job_id}", response_model=StatusResponse, tags=["Video"])
def get_status(job_id: str, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    status = job.get("status", "unknown")

    if status == "success":
        return StatusResponse(
            job_id=job_id,
            status="success",
            download_url=f"/file/{job_id}",
            progress={
                "title": job.get("title"),
                "duration": job.get("duration"),
                "filesize": job.get("filesize"),
            },
        )

    if status == "failure":
        return StatusResponse(job_id=job_id, status="failure", error=job.get("error"))

    if status == "post_processing":
        return StatusResponse(
            job_id=job_id,
            status="post_processing",
            progress={"message": "FFmpeg post-processing..."},
        )

    if status == "progress":
        return StatusResponse(job_id=job_id, status="progress", progress=job)

    return StatusResponse(job_id=job_id, status=status)


@app.get("/file/{job_id}", tags=["Video"])
def download_file(
    job_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    rate_limit(request, api_key)

    job = get_job(job_id)
    if not job or job.get("status") != "success":
        raise HTTPException(status_code=404, detail="File not available")

    filepath = _find_output_file(job_id)
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File expired or not found")

    background_tasks.add_task(os.remove, filepath)

    return FileResponse(
        path=filepath,
        filename=os.path.basename(filepath),
        media_type="application/octet-stream",
    )


@app.delete("/file/{job_id}", tags=["Video"])
def delete_file(job_id: str, request: Request, api_key: str = Depends(get_api_key)):
    rate_limit(request, api_key)

    filepath = _find_output_file(job_id)
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
        return {"message": "File deleted"}
    return {"message": "File already deleted or not found"}
