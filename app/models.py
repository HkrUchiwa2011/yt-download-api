from pydantic import BaseModel, field_validator
from typing import Literal
from enum import Enum


class VideoFormat(str, Enum):
    mp4 = "mp4"
    mp3 = "mp3"
    webm = "webm"


class VideoQuality(str, Enum):
    best = "best"
    q1080 = "1080p"
    q720 = "720p"
    q480 = "480p"
    q360 = "360p"
    audio_only = "audio_only"


class DownloadRequest(BaseModel):
    url: str
    format: VideoFormat = VideoFormat.mp4
    quality: VideoQuality = VideoQuality.best
    webhook_url: str | None = None

    @field_validator("url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        allowed = ("youtube.com/watch", "youtu.be/", "youtube.com/shorts/")
        if not any(d in v for d in allowed):
            raise ValueError("Must be a valid YouTube URL")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("webhook_url must be a valid HTTP/HTTPS URL")
        return v


class DownloadResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatus(str, Enum):
    pending = "pending"
    started = "started"
    progress = "progress"
    post_processing = "post_processing"
    success = "success"
    failure = "failure"


class StatusResponse(BaseModel):
    job_id: str
    status: Literal["pending", "started", "progress", "post_processing", "success", "failure"]
    progress: dict | None = None
    download_url: str | None = None
    error: str | None = None


class VideoInfo(BaseModel):
    title: str
    duration: int
    uploader: str | None
    thumbnail: str | None
    formats: list[dict]
    filesize_approx: int | None
