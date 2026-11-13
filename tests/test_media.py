"""Real yt-dlp transfers and FFmpeg processing using tiny local media fixtures."""

import functools
import http.server
import os
import shutil
import struct
import subprocess
import threading

import httpx
import pytest
import yt_dlp

from app.jobs import enqueue_download, get_job
from app.models import DownloadRequest
from app.storage import job_directory
from app.tasks import run_download


@pytest.fixture
def media_server(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Media integration requires FFmpeg and ffprobe")
    source = tmp_path / "source"
    source.mkdir()
    fixture_ffmpeg = os.environ.get("FIXTURE_FFMPEG", "ffmpeg")
    common = [
        fixture_ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x90:r=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440",
        "-t",
        "0.4",
        "-threads",
        "1",
    ]
    subprocess.run(
        [
            *common,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source / "source.mp4"),
        ],
        check=True,
        timeout=20,
    )
    subprocess.run(
        [*common, "-c:v", "libvpx-vp9", "-c:a", "libopus", str(source / "source.webm")],
        check=True,
        timeout=20,
    )
    for extension in ("mp4", "webm"):
        for stream, flag in (("video", "-an"), ("audio", "-vn")):
            subprocess.run(
                [
                    fixture_ffmpeg,
                    "-v",
                    "error",
                    "-i",
                    str(source / f"source.{extension}"),
                    flag,
                    "-c",
                    "copy",
                    str(source / f"{stream}.{extension}"),
                ],
                check=True,
                timeout=20,
            )
    subprocess.run(
        [
            fixture_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "0.4",
            str(source / "source.wav"),
        ],
        check=True,
        timeout=20,
    )

    subprocess.run(
        [
            fixture_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "50",
            "-c:a",
            "aac",
            "-b:a",
            "32k",
            str(source / "long.m4a"),
        ],
        check=True,
        timeout=20,
    )

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(source))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize(
    ("format", "source_ext", "vcodec", "acodec"),
    [
        ("mp4", "mp4", "h264", "aac"),
        ("webm", "webm", "vp9", "opus"),
        ("mp3", "wav", "none", "pcm_s16le"),
        ("mp3", "mp4", "h264", "aac"),
        ("mp3", "webm", "vp9", "opus"),
    ],
)
def test_actual_transfer_and_ffmpeg_output(
    redisdb, settings, monkeypatch, media_server, format, source_ext, vcodec, acodec
):
    original = yt_dlp.YoutubeDL

    class LocalFixtureYDL(original):
        def extract_info(self, url, download=False, **kwargs):
            return {
                "id": "fixture",
                "title": "Fixture",
                "duration": 1,
                "url": f"{media_server}/source.{source_ext}",
                "ext": source_ext,
                "format_id": "fixture",
                "vcodec": vcodec,
                "acodec": acodec,
            }

    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", LocalFixtureYDL)
    identifier = enqueue_download(
        DownloadRequest(url="https://youtu.be/BaW_jenozKc", format=format)
    )
    run_download(identifier, "https://youtu.be/BaW_jenozKc", format, "best")
    job = get_job(identifier)
    assert job["status"] == "success", job
    output = job_directory(identifier) / job["filename"]
    assert output.stat().st_size > 0
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert format in probe.stdout
    assert list(output.parent.iterdir()) == [output]


@pytest.mark.parametrize("format", ["mp4", "webm"])
def test_actual_separate_stream_merge(redisdb, settings, monkeypatch, media_server, format):
    original = yt_dlp.YoutubeDL

    class LocalFixtureYDL(original):
        def extract_info(self, url, download=False, **kwargs):
            return {
                "id": "fixture",
                "title": "Separate streams",
                "duration": 1,
                "extractor": "youtube",
                "extractor_key": "Youtube",
                "ext": format,
                "formats": [
                    {
                        "url": f"{media_server}/video.{format}",
                        "ext": format,
                        "format_id": "video",
                        "protocol": "http",
                        "vcodec": "h264" if format == "mp4" else "vp9",
                        "acodec": "none",
                    },
                    {
                        "url": f"{media_server}/audio.{format}",
                        "ext": "m4a" if format == "mp4" else format,
                        "format_id": "audio",
                        "protocol": "http",
                        "vcodec": "none",
                        "acodec": "aac" if format == "mp4" else "opus",
                    },
                ],
            }

    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", LocalFixtureYDL)
    identifier = enqueue_download(
        DownloadRequest(url="https://youtu.be/BaW_jenozKc", format=format)
    )
    run_download(identifier, "https://youtu.be/BaW_jenozKc", format, "best")
    job = get_job(identifier)
    assert job["status"] == "success", job
    output = job_directory(identifier) / job["filename"]
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", str(output)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert "codec_type=video" in probe.stdout
    assert "codec_type=audio" in probe.stdout
    assert list(output.parent.iterdir()) == [output]


@pytest.mark.parametrize("case", ["encryption", "hdr"])
def test_native_security_regressions(case):
    binary = os.environ.get("NATIVE_TEST_BINARY")
    if not binary:
        pytest.skip("Requires Docker's patched native library test binary")
    subprocess.run([binary, case], check=True, timeout=5)


def test_excessive_mp4_encryption_metadata_is_rejected(tmp_path, media_server):
    if not os.environ.get("NATIVE_TEST_BINARY"):
        pytest.skip("Requires Docker's bounded MOV parser")
    response = httpx.get(f"{media_server}/source.mp4", timeout=5, trust_env=False)
    response.raise_for_status()
    original = response.content
    # Insert 65 small DRM records into the existing movie atom, after its tracks.
    records = (struct.pack(">I4s", 32, b"pssh") + bytes(24)) * 65
    offset = 0
    crafted = bytearray()
    while offset < len(original):
        size, kind = struct.unpack_from(">I4s", original, offset)
        assert size >= 8
        atom = original[offset : offset + size]
        if kind == b"moov":
            atom = struct.pack(">I4s", size + len(records), kind) + atom[8:] + records
        crafted.extend(atom)
        offset += size
    path = tmp_path / "crafted.mp4"
    path.write_bytes(crafted)
    result = subprocess.run(
        ["ffprobe", "-v", "error", str(path)], capture_output=True, text=True, timeout=5
    )
    assert result.returncode != 0
    assert "Too many PSSH" in result.stderr


def test_postprocessing_cannot_grow_past_size_limit(redisdb, settings, monkeypatch, media_server):
    original = yt_dlp.YoutubeDL

    class LocalFixtureYDL(original):
        def extract_info(self, url, download=False, **kwargs):
            return {
                "id": "fixture",
                "title": "Fixture",
                "duration": 50,
                "url": f"{media_server}/long.m4a",
                "ext": "m4a",
                "format_id": "fixture",
                "vcodec": "none",
                "acodec": "aac",
            }

    monkeypatch.setattr("app.tasks.yt_dlp.YoutubeDL", LocalFixtureYDL)
    identifier = enqueue_download(DownloadRequest(url="https://youtu.be/BaW_jenozKc", format="mp3"))
    run_download(identifier, "https://youtu.be/BaW_jenozKc", "mp3", "best")
    job = get_job(identifier)
    assert job["status"] == "failure", job
    assert "size limit" in job["error"]
    assert not job_directory(identifier).exists()
