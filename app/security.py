"""Canonical video URLs and DNS-pinned outbound webhook requests."""

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import socket
import time
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def youtube_url(value: str) -> str:
    if len(value) > 2048 or any(ord(char) <= 32 for char in value) or "\\" in value:
        raise ValueError("Must be a valid HTTPS YouTube video URL")
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            raise ValueError
        if parts.hostname == "youtu.be":
            video_id = parts.path.removeprefix("/")
        elif parts.hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
        }:
            if parts.path == "/watch":
                ids = parse_qs(parts.query).get("v", [])
                video_id = ids[0] if len(ids) == 1 else ""
            elif parts.path.startswith(("/shorts/", "/embed/", "/live/")):
                video_id = parts.path.split("/")[-1]
                if parts.path.count("/") != 2:
                    raise ValueError
            else:
                raise ValueError
        else:
            raise ValueError
        if not VIDEO_ID.fullmatch(video_id):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("Must be a valid HTTPS YouTube video URL") from exc
    return f"https://www.youtube.com/watch?v={video_id}"


def normalize_hostname(host: str) -> str:
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Invalid webhook hostname") from exc
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
        raise ValueError("Use exact webhook hostnames without wildcards or ports")
    return host


def webhook_url(value: str, allowed_hosts: list[str]) -> str:
    if len(value) > 2048 or any(ord(char) <= 32 for char in value) or "\\" in value:
        raise ValueError("Invalid webhook URL")
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            raise ValueError
        host = normalize_hostname(parts.hostname or "")
        if host not in allowed_hosts or parts.fragment:
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".localhost", ".local", ".internal")):
                raise ValueError from None
        else:
            if not address.is_global:
                raise ValueError
        return urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid or unauthorized HTTPS webhook URL") from exc


def public_addresses(host: str) -> list[str]:
    addresses = list(
        dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
    )
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Webhook DNS must resolve exclusively to public addresses")
    return addresses


def notify_webhook(url: str, payload: dict) -> bool:
    from app.config import get_settings

    settings = get_settings()
    try:
        parts = urlsplit(webhook_url(url, settings.WEBHOOK_ALLOWED_HOSTS))
        addresses = public_addresses(parts.hostname)
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            settings.WEBHOOK_SECRET.get_secret_value().encode(),
            timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        # Prevent DNS rebinding while preserving TLS hostname verification and Host.
        for attempt in range(3):
            address = addresses[attempt % len(addresses)]
            authority = f"[{address}]" if ":" in address else address
            pinned_url = urlunsplit(("https", authority, parts.path, parts.query, ""))
            try:
                with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
                    with client.stream(
                        "POST",
                        pinned_url,
                        content=body,
                        headers={
                            "Host": parts.hostname,
                            "Content-Type": "application/json",
                            "X-YT-Timestamp": timestamp,
                            "X-YT-Signature": f"sha256={signature}",
                        },
                        extensions={"sni_hostname": parts.hostname},
                    ) as response:
                        if response.is_success:
                            return True
                        if response.status_code < 500:
                            break
            except httpx.RequestError:
                pass
            if attempt < 2:
                time.sleep(attempt + 1)
    except (ValueError, OSError):
        pass
    logger.warning("Webhook delivery failed for job %s", payload.get("job_id"))
    return False
