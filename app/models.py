from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.security import webhook_url, youtube_url


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


JobStatus = Literal["pending", "started", "progress", "post_processing", "success", "failure"]


class DownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    format: VideoFormat = VideoFormat.mp4
    quality: VideoQuality = VideoQuality.best
    webhook_url: str | None = None

    @field_validator("url")
    @classmethod
    def validate_video(cls, value: str) -> str:
        return youtube_url(value)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, value: str | None) -> str | None:
        from app.config import get_settings

        return webhook_url(value, get_settings().WEBHOOK_ALLOWED_HOSTS) if value else None

    @model_validator(mode="after")
    def valid_combination(self):
        if self.quality == VideoQuality.audio_only and self.format != VideoFormat.mp3:
            raise ValueError("audio_only requires format=mp3")
        return self


class DownloadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: dict | None = None
    download_url: str | None = None
    error: str | None = None


class VideoInfo(BaseModel):
    title: str
    duration: int | None
    uploader: str | None = None
    thumbnail: str | None = None
    formats: list[dict]
    filesize_approx: int | None = None
