import os
import time
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def cleanup_old_files():
    if not os.path.exists(settings.TMP_DIR):
        return

    now = time.time()
    ttl = settings.FILE_TTL_MINUTES * 60
    removed = 0

    for filename in os.listdir(settings.TMP_DIR):
        filepath = os.path.join(settings.TMP_DIR, filename)
        try:
            if os.path.isfile(filepath) and (now - os.path.getmtime(filepath)) > ttl:
                os.remove(filepath)
                removed += 1
        except Exception as e:
            logger.warning(f"Cleanup failed for {filepath}: {e}")

    if removed:
        logger.info(f"Cleanup: removed {removed} expired file(s)")
