import hashlib
import hmac
import json
import socket
from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import DownloadRequest
from app.security import notify_webhook, public_addresses, webhook_url, youtube_url

VIDEO_ID = "BaW_jenozKc"


@pytest.mark.parametrize(
    "url",
    [
        f"https://youtu.be/{VIDEO_ID}?list=evil",
        f"https://www.youtube.com/watch?v={VIDEO_ID}&list=evil",
        f"https://m.youtube.com/shorts/{VIDEO_ID}",
        f"https://youtube.com/embed/{VIDEO_ID}",
        f"https://youtube.com/live/{VIDEO_ID}",
    ],
)
def test_canonical_youtube_url(url):
    assert youtube_url(url) == f"https://www.youtube.com/watch?v={VIDEO_ID}"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/?next=youtube.com/watch?v=BaW_jenozKc",
        "https://youtube.com.evil.org/watch?v=BaW_jenozKc",
        "https://youtube.com@127.0.0.1/watch?v=BaW_jenozKc",
        "http://youtube.com/watch?v=BaW_jenozKc",
        "file:///youtube.com/watch",
        "https://youtu.be/not-a-video-id",
        "https://youtube.com:444/watch?v=BaW_jenozKc",
        "https://youtube.com/watch?v=BaW_jenozKc&v=BaW_jenozKc",
        "https://youtube.com/shorts/other/BaW_jenozKc",
        "https://youtube.com\\@127.0.0.1/watch?v=BaW_jenozKc",
        "https://youtu.be/BaW_jenozKc\n",
        "https://youtube.com/playlist?list=xxx",
    ],
)
def test_reject_non_youtube_urls(url):
    with pytest.raises(ValueError):
        youtube_url(url)


@pytest.mark.parametrize(
    "key",
    [
        "changeme",
        "change-this-to-a-strong-secret",
        "x" * 31,
        "replace-with-a-random-secret-of-at-least-32-characters",
    ],
)
def test_weak_keys_rejected(key):
    with pytest.raises(ValidationError):
        Settings(API_KEY=key)


def test_webhooks_need_allowlist_and_signing_secret(settings):
    with pytest.raises(ValidationError):
        Settings(API_KEY="test" * 8, WEBHOOK_ALLOWED_HOSTS=["example.org"])
    with pytest.raises(ValidationError):
        DownloadRequest(
            url=f"https://youtu.be/{VIDEO_ID}", webhook_url="https://example.org/callback"
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/callback",
        "https://127.0.0.1/callback",
        "https://example.org@127.0.0.1/callback",
        "https://example.org:8443/callback",
        "https://example.org.evil.org/callback",
        "https://localhost/callback",
        "https://10.1.2.3/callback",
    ],
)
def test_webhook_targets_restricted(url):
    with pytest.raises(ValueError):
        webhook_url(url, ["example.org", "127.0.0.1", "localhost", "10.1.2.3"])


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "100.64.0.1"]
)
def test_dns_private_or_mixed_addresses_rejected(monkeypatch, address):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
        ],
    )
    with pytest.raises(ValueError):
        public_addresses("example.org")


def test_webhook_is_signed_and_dns_pinned(settings, monkeypatch, httpx_mock):
    settings.WEBHOOK_ALLOWED_HOSTS = ["example.org"]
    from pydantic import SecretStr

    settings.WEBHOOK_SECRET = SecretStr("secret" * 8)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    httpx_mock.add_response(url="https://93.184.216.34/callback", status_code=204)
    payload = {"job_id": "job", "status": "success"}
    assert notify_webhook("https://example.org/callback", payload)
    request = httpx_mock.get_request()
    assert urlsplit(str(request.url)).hostname == "93.184.216.34"
    assert request.headers["Host"] == "example.org"
    assert request.extensions["sni_hostname"] == "example.org"
    assert json.loads(request.content) == payload
    digest = hmac.new(
        b"secret" * 8,
        request.headers["X-YT-Timestamp"].encode() + b"." + request.content,
        hashlib.sha256,
    ).hexdigest()
    assert request.headers["X-YT-Signature"] == "sha256=" + digest


def test_webhook_redirect_not_followed(settings, monkeypatch, httpx_mock):
    from pydantic import SecretStr

    settings.WEBHOOK_ALLOWED_HOSTS = ["example.org"]
    settings.WEBHOOK_SECRET = SecretStr("secret" * 8)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    httpx_mock.add_response(
        url="https://93.184.216.34/callback",
        status_code=302,
        headers={"Location": "https://127.0.0.1/private"},
    )
    assert not notify_webhook("https://example.org/callback", {"job_id": "job"})
    assert len(httpx_mock.get_requests()) == 1


def test_private_dns_never_opens_a_connection(settings, monkeypatch, httpx_mock):
    from pydantic import SecretStr

    settings.WEBHOOK_ALLOWED_HOSTS = ["example.org"]
    settings.WEBHOOK_SECRET = SecretStr("secret" * 8)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    assert not notify_webhook("https://example.org/callback", {"job_id": "job"})
    assert not httpx_mock.get_requests()
