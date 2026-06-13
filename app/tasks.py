import os
import json
import httpx
import yt_dlp
import redis as redis_client

from app.config import get_settings

settings = get_settings()

QUALITY_MAP = {
    "best":       "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "1080p":      "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
    "720p":       "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
    "480p":       "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
    "360p":       "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
    "audio_only": "bestaudio/best",
}

FORMAT_POSTPROCESS = {
    "mp4":  [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    "mp3":  [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "webm": [],
}

BASE_YDL_OPTS = {
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "tv_embedded"],
        }
    },
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Mobile Safari/537.36"
        )
    },
    "noplaylist": True,
    "quiet": True,
}


def get_redis():
    return redis_client.from_url(settings.REDIS_URL, decode_responses=True)


def set_job(job_id: str, data: dict):
    r = get_redis()
    r.setex(f"job:{job_id}", settings.FILE_TTL_MINUTES * 60, json.dumps(data))


def get_job(job_id: str) -> dict | None:
    raw = get_redis().get(f"job:{job_id}")
    return json.loads(raw) if raw else None


def get_video_info(url: str) -> dict:
    opts = {**BASE_YDL_OPTS}
    if settings.PROXY_URL:
        opts["proxy"] = settings.PROXY_URL

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = [
        {
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "resolution": f.get("resolution") or f.get("format_note"),
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec"),
        }
        for f in info.get("formats", [])
        if f.get("ext") in ("mp4", "webm", "m4a", "mp3")
    ]

    return {
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
        "formats": formats,
        "filesize_approx": info.get("filesize_approx"),
    }


def _progress_hook(job_id: str):
    def hook(d):
        if d["status"] == "downloading":
            set_job(job_id, {
                "status": "progress",
                "downloaded_bytes": d.get("downloaded_bytes", 0),
                "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate", 0),
                "speed": round(d.get("speed") or 0, 2),
                "eta": d.get("eta", 0),
            })
        elif d["status"] == "finished":
            set_job(job_id, {"status": "post_processing"})
    return hook


def _find_output_file(job_id: str) -> str | None:
    if not os.path.exists(settings.TMP_DIR):
        return None
    for f in os.listdir(settings.TMP_DIR):
        if f.startswith(job_id) and not f.endswith((".part", ".ytdl")):
            return os.path.join(settings.TMP_DIR, f)
    return None


def _notify_webhook(webhook_url: str, payload: dict):
    try:
        with httpx.Client(timeout=10) as client:
            client.post(webhook_url, json=payload)
    except Exception:
        pass


def run_download(job_id: str, url: str, format: str, quality: str, webhook_url: str | None = None):
    os.makedirs(settings.TMP_DIR, exist_ok=True)
    out_template = os.path.join(settings.TMP_DIR, f"{job_id}.%(ext)s")

    set_job(job_id, {"status": "started"})

    opts = {
        **BASE_YDL_OPTS,
        "format": QUALITY_MAP.get(quality, QUALITY_MAP["best"]),
        "postprocessors": FORMAT_POSTPROCESS.get(format, []),
        "outtmpl": out_template,
        "merge_output_format": format if format != "mp3" else None,
        "max_filesize": settings.MAX_FILESIZE_MB * 1024 * 1024,
        "progress_hooks": [_progress_hook(job_id)],
    }

    if settings.PROXY_URL:
        opts["proxy"] = settings.PROXY_URL

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration", 0)

            if duration > settings.MAX_DURATION_SECONDS:
                raise ValueError(
                    f"Video too long ({duration}s). Maximum allowed: {settings.MAX_DURATION_SECONDS}s"
                )

            ydl.download([url])

        filepath = _find_output_file(job_id)
        if not filepath:
            raise FileNotFoundError("Output file not found after download")

        result = {
            "status": "success",
            "filepath": filepath,
            "title": info.get("title", ""),
            "duration": duration,
            "filesize": os.path.getsize(filepath),
        }
        set_job(job_id, result)

        if webhook_url:
            _notify_webhook(webhook_url, {"job_id": job_id, **result, "filepath": None})

    except Exception as exc:
        error_payload = {"status": "failure", "error": str(exc)}
        set_job(job_id, error_payload)

        if webhook_url:
            _notify_webhook(webhook_url, {"job_id": job_id, **error_payload})
