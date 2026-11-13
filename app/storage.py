import os
import shutil
import stat
from pathlib import Path
from uuid import UUID

from app.config import get_settings


def canonical_job_id(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("Invalid job identifier")
    return value


def job_directory(job_id: str) -> Path:
    root = get_settings().TMP_DIR
    directory = root / canonical_job_id(job_id)
    if root.is_symlink() or directory.is_symlink():
        raise ValueError("Unsafe download directory")
    return directory


def ensure_storage():
    root = get_settings().TMP_DIR
    if root.is_symlink():
        raise ValueError("TMP_DIR cannot be a symlink")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.getuid():
        raise ValueError("TMP_DIR must be owned by the service user")
    root.chmod(0o700)


def check_free_space(*, reservations: int = 1):
    settings = get_settings()
    ensure_storage()
    required = (settings.MAX_FILESIZE_MB * 2 * reservations + settings.MIN_FREE_SPACE_MB) * 1024**2
    if shutil.disk_usage(settings.TMP_DIR).free < required:
        raise ValueError("Insufficient free storage for a download")


def remove_job_files(job_id: str):
    directory = job_directory(job_id)
    if directory.exists():
        shutil.rmtree(directory)


def open_output(job_id: str, filename: str):
    if filename not in {"output.mp4", "output.mp3", "output.webm"}:
        raise FileNotFoundError("Invalid output filename")
    directory_fd = os.open(job_directory(job_id), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise FileNotFoundError("Output is not a regular file")
    return os.fdopen(fd, "rb")
