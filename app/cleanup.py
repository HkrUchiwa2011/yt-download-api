import logging
import time

from app.config import get_settings
from app.jobs import ACTIVE, get_job
from app.storage import canonical_job_id, remove_job_files

logger = logging.getLogger(__name__)


def cleanup_old_files():
    settings = get_settings()
    if not settings.TMP_DIR.exists():
        return
    for directory in settings.TMP_DIR.iterdir():
        try:
            canonical_job_id(directory.name)
            if directory.is_symlink() or not directory.is_dir():
                continue
            job = get_job(directory.name)
            if job and job["status"] in ACTIVE:
                continue
            expiry = (
                job["expires_at"]
                if job
                else directory.stat().st_mtime + settings.FILE_TTL_MINUTES * 60
            )
            if time.time() >= expiry:
                remove_job_files(directory.name)
        except (OSError, ValueError):
            logger.warning("Unable to clean a download directory")
