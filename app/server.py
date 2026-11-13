"""Supervise embedded workers when a platform cannot share volumes across services."""

import os
import signal
import subprocess
import sys
import time

from app.config import get_settings


def main():
    settings = get_settings()
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for _ in range(settings.EMBEDDED_WORKERS):
            children.append(subprocess.Popen([sys.executable, "-m", "app.worker"]))
        children.append(
            subprocess.Popen(  # noqa: S603 - fixed executable and argv, no shell
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "0.0.0.0",  # noqa: S104, S603 - container listener, fixed argv without shell
                    "--port",
                    os.getenv("PORT", "8000"),
                    "--http",
                    "h11",
                    "--h11-max-incomplete-event-size",
                    "16384",
                    "--no-proxy-headers",
                    "--no-server-header",
                    "--no-access-log",
                    "--limit-concurrency",
                    "32",
                ]
            )
        )
        while not stopping and all(child.poll() is None for child in children):
            time.sleep(0.25)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 25
        for child in children:
            try:
                child.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                # RQ treats a second shutdown signal as a forced stop and kills its work horse.
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
    return 0 if stopping else 1


if __name__ == "__main__":
    raise SystemExit(main())
