import logging
import multiprocessing
import os
import time

import yt_dlp
from rq.timeouts import JobTimeoutException

from app.config import get_settings
from app.jobs import release_slot, set_job
from app.models import DownloadRequest
from app.security import notify_webhook, youtube_url
from app.storage import check_free_space, job_directory, remove_job_files

logger = logging.getLogger(__name__)


class DownloadRejected(ValueError):
    pass


class ExtractorLogger:
    # yt-dlp errors can contain proxy credentials or signed CDN URLs.
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def base_options():
    settings = get_settings()
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": ExtractorLogger(),
        "socket_timeout": settings.SOCKET_TIMEOUT_SECONDS,
        "retries": 2,
        "fragment_retries": 2,
        "extractor_retries": 1,
        "enable_file_urls": False,
        "js_runtimes": {"deno": {}},
        "remote_components": set(),
        "cachedir": False,
        "proxy": "",
    }
    if settings.PROXY_URL:
        opts["proxy"] = settings.PROXY_URL.get_secret_value()
    return opts


def format_options(format: str, quality: str):
    height = f"[height<={quality[:-1]}]" if quality.endswith("p") else ""
    if format == "mp3":
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        }
    if format == "webm":
        selection = f"bestvideo[ext=webm]{height}+bestaudio[ext=webm]/best[ext=webm]{height}"
    else:
        selection = f"bestvideo[ext=mp4]{height}+bestaudio[ext=m4a]/best[ext=mp4]{height}"
    return {"format": selection, "merge_output_format": format}


def _extract_info(url: str):
    with yt_dlp.YoutubeDL(base_options()) as ydl:
        info = ydl.extract_info(youtube_url(url), download=False)
    if not info or info.get("_type") in {"playlist", "multi_video"}:
        raise ValueError("Not a video")
    return {
        "title": info.get("title", ""),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
        "filesize_approx": info.get("filesize_approx"),
        "formats": [
            {
                key: f.get(key)
                for key in ("format_id", "ext", "resolution", "filesize", "vcodec", "acodec")
            }
            for f in info.get("formats", [])
            if f.get("ext") in {"mp4", "webm", "m4a", "mp3"}
        ],
    }


def _info_child(connection, url):
    try:
        connection.send(_extract_info(url))
    except Exception:
        connection.send(None)
    finally:
        connection.close()


def get_video_info(url: str):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_info_child, args=(child, url))
    process.start()
    child.close()
    try:
        if not parent.poll(get_settings().SOCKET_TIMEOUT_SECONDS * 3):
            raise ValueError("Metadata timed out")
        result = parent.recv()
        if result is None:
            raise ValueError("Metadata unavailable")
        return result
    except EOFError:
        raise ValueError("Metadata unavailable") from None
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join()


def run_download(job_id: str, url: str, format: str, quality: str, webhook_url: str | None = None):
    settings = get_settings()
    directory = job_directory(job_id)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    deadline = time.monotonic() + settings.JOB_TIMEOUT_SECONDS
    last_update = 0.0
    limit = settings.MAX_FILESIZE_MB * 1024**2

    def hook(data):
        nonlocal last_update
        if time.monotonic() > deadline:
            raise DownloadRejected("Download timed out")
        if (data.get("downloaded_bytes") or 0) > limit:
            raise DownloadRejected("File exceeds the configured size limit")
        if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > limit:
            raise DownloadRejected("Download exceeds the configured storage limit")
        check_free_space(reservations=0)
        if data["status"] == "finished":
            set_job(
                job_id, {"status": "post_processing", "progress": {"message": "Processing media"}}
            )
        elif time.monotonic() - last_update >= 1:
            last_update = time.monotonic()
            set_job(
                job_id,
                {
                    "status": "progress",
                    "progress": {
                        key: data.get(key)
                        for key in (
                            "downloaded_bytes",
                            "total_bytes",
                            "total_bytes_estimate",
                            "speed",
                            "eta",
                        )
                    },
                },
            )

    payload = None
    try:
        body = DownloadRequest(url=url, format=format, quality=quality, webhook_url=webhook_url)
        url = body.url
        check_free_space()
        set_job(job_id, {"status": "started"})
        opts = {
            **base_options(),
            **format_options(format, quality),
            "outtmpl": str(directory / "output.%(ext)s"),
            "max_filesize": limit,
            "postprocessor_args": {"ffmpeg_o": ["-fs", str(limit)]},
            "progress_hooks": [hook],
            "overwrites": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url(url), download=False)
            duration = info.get("duration") if info else None
            if not info or info.get("is_live") or duration is None:
                raise DownloadRejected("Live or unknown-duration videos cannot be downloaded")
            if duration > settings.MAX_DURATION_SECONDS:
                raise DownloadRejected("Video exceeds the configured duration limit")
            # Process the already extracted result: avoid a second metadata request.
            ydl.process_ie_result(info, download=True)
        filename = f"output.{format}"
        output = directory / filename
        if not output.is_file() or output.is_symlink():
            raise DownloadRejected("Requested media format is unavailable")
        if output.stat().st_size >= limit:
            raise DownloadRejected("File exceeds the configured size limit")
        for intermediate in directory.iterdir():
            if intermediate != output and intermediate.is_file():
                intermediate.unlink()
        os.utime(directory, None)
        payload = {
            "status": "success",
            "title": info.get("title", ""),
            "duration": duration,
            "filesize": output.stat().st_size,
            "filename": filename,
        }
        set_job(job_id, payload)
    except Exception as exc:
        if isinstance(exc, JobTimeoutException):
            error = "Download timed out"
        elif isinstance(exc, DownloadRejected):
            error = str(exc)
        else:
            error = "Download failed. Video unavailable or upstream access denied."
        logger.warning("Download failed for job %s (%s)", job_id, type(exc).__name__)
        remove_job_files(job_id)
        payload = {"status": "failure", "error": error}
        set_job(job_id, payload)
    finally:
        release_slot(job_id)
    if webhook_url and payload:
        notify_webhook(
            webhook_url,
            {
                "job_id": job_id,
                **{key: value for key, value in payload.items() if key != "filename"},
            },
        )
