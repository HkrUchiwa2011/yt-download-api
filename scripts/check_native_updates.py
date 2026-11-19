"""Watch source releases and advisory changes that package scans cannot inventory."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
TRACKER = "https://security-tracker.debian.org/tracker/data/json"


def fetch(url, *, max_bytes=2 * 1024**2):
    headers = {}
    token = os.getenv("GITHUB_TOKEN")
    target = urlsplit(url)
    if token and target.scheme == "https" and target.netloc == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ValueError("Native update response exceeds the size limit")
    return body.decode()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def changes(data, reviewed):
    problems = []
    for package, baseline in reviewed["packages"].items():
        entries = data[package]
        if not entries:
            raise ValueError(f"Empty tracker result for {package}")
        known = set(baseline["known_ids"])
        for identifier, entry in sorted(entries.items()):
            if identifier not in known:
                problems.append(f"New advisory: {package} {identifier}")
            if entry.get("releases", {}).get("sid", {}).get("status") == "open":
                assessment = baseline["open"].get(identifier)
                if assessment is None:
                    problems.append(f"Unreviewed open advisory: {package} {identifier}")
                elif digest(entry["description"]) != assessment["description_sha256"]:
                    problems.append(f"Changed advisory: {package} {identifier}")
    return problems


def release_changes(reviewed, ffmpeg, expat, python_index):
    expected = reviewed["versions"]
    ffmpeg_version = re.search(r"ffmpeg-([0-9.]+)\.tar\.xz", ffmpeg).group(1)
    expat_version = json.loads(expat)["tag_name"].removeprefix("R_").replace("_", ".")
    series = ".".join(expected["python"].split(".")[:2])
    versions = re.findall(r'href="(' + re.escape(series) + r'\.\d+)/"', python_index)
    python_version = max(versions, key=lambda value: tuple(map(int, value.split("."))))
    latest = {"ffmpeg": ffmpeg_version, "expat": expat_version, "python": python_version}
    return [
        f"New {name} release: {expected[name]} -> {value}"
        for name, value in latest.items()
        if expected[name] != value
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracker", type=Path)
    args = parser.parse_args()
    reviewed = json.loads((ROOT / "security/native-reviewed.json").read_text())
    dockerfile = (ROOT / "Dockerfile").read_text()
    problems = []
    for name, argument in (
        ("ffmpeg", "FFMPEG_VERSION"),
        ("expat", "EXPAT_VERSION"),
        ("python", "PYTHON_VERSION"),
    ):
        installed = re.search(r"^ARG " + argument + r"=([^\n]+)", dockerfile, re.M).group(1)
        if installed != reviewed["versions"][name]:
            problems.append(f"Native version review required: {name} {installed}")
    data = json.loads(
        args.tracker.read_text() if args.tracker else fetch(TRACKER, max_bytes=256 * 1024**2)
    )
    problems.extend(changes(data, reviewed))
    problems.extend(
        release_changes(
            reviewed,
            fetch("https://ffmpeg.org/download.html"),
            fetch("https://api.github.com/repos/libexpat/libexpat/releases/latest"),
            fetch("https://www.python.org/ftp/python/"),
        )
    )
    issue = json.loads(fetch("https://api.github.com/repos/libexpat/libexpat/issues/1160"))
    if digest(issue["body"]) != reviewed["expat_pending_issue_sha256"]:
        problems.append("Expat's pending-security-issues list changed; review issue 1160")
    print(
        "Native release/advisory watch: "
        + ("review required" if problems else "no unreviewed changes")
    )
    for problem in problems:
        print(problem)
    print(
        "Undisclosed upstream issues still require human review; this is not a vulnerability certificate."
    )
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
