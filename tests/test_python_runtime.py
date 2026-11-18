"""Security regressions for the Python library shipped in Docker."""

import io
import os
from email.message import Message
from http.client import HTTPResponse, IncompleteRead
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.request import Request

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("PATCHED_PYTHON_RUNTIME"), reason="Requires patched Docker Python"
)


class MemorySocket:
    def __init__(self, data):
        self.stream = io.BytesIO(data)

    def makefile(self, mode):
        return self.stream


@pytest.mark.parametrize("size", [b"-5", b"+5", b"0x5", b"1_f", b" 5"])
def test_invalid_chunk_size_closes_response(size):
    socket = MemorySocket(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + size + b"\r\nHELLO\r\n0\r\n\r\n"
    )
    with HTTPResponse(socket, method="GET") as response:
        response.begin()
        with pytest.raises(IncompleteRead):
            response.read()
        assert response.isclosed()


@pytest.mark.parametrize("size", [b"a", b"A", b"a;name=value"])
def test_valid_chunk_size_and_extensions(size):
    socket = MemorySocket(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        + size
        + b"\r\n0123456789\r\n0\r\n\r\n"
    )
    with HTTPResponse(socket, method="GET") as response:
        response.begin()
        assert response.read() == b"0123456789"


@pytest.mark.parametrize("length", [b"+5", b"5_0", b"5 0", b"-5"])
def test_invalid_content_length_uses_connection_close(length):
    socket = MemorySocket(b"HTTP/1.1 200 OK\r\nContent-Length: " + length + b"\r\n\r\nHello\r\n")
    with HTTPResponse(socket, method="GET") as response:
        response.begin()
        assert response.length is None
        assert response.will_close
        assert response.read() == b"Hello\r\n"


@pytest.mark.parametrize("length", [b"7", b"7 ", b"7\t", b"7 \t ", b" 7 "])
def test_valid_content_length_preserves_persistent_connection_framing(length):
    socket = MemorySocket(
        b"HTTP/1.1 200 OK\r\nContent-Length: " + length + b"\r\n\r\nHello\r\nextra"
    )
    with HTTPResponse(socket, method="GET") as response:
        response.begin()
        assert response.length == 7
        assert not response.will_close
        assert response.read() == b"Hello\r\n"


class CookieResponse:
    def __init__(self, header):
        self.headers = Message()
        self.headers["Set-Cookie"] = header

    def info(self):
        return self.headers


def extract(jar, host, header):
    jar.extract_cookies(CookieResponse(header), Request(host))  # noqa: S310 - metadata only, no I/O


@pytest.mark.parametrize("expiration", ["Max-Age=0", "Expires=Thu, 01 Jan 1970 00:00:00 GMT"])
def test_expired_cookie_cannot_delete_another_domains_cookie(expiration):
    jar = CookieJar()
    extract(jar, "https://www.victim.test/", "session=value; Domain=.victim.test; Path=/")
    extract(
        jar, "https://www.attacker.test/", f"session=x; Domain=.victim.test; Path=/; {expiration}"
    )
    assert len(jar) == 1
    extract(jar, "https://www.victim.test/", "session=x; Domain=.victim.test; Path=/; Max-Age=0")
    assert len(jar) == 0


def test_expired_cookie_obeys_path_policy():
    jar = CookieJar(DefaultCookiePolicy(strict_ns_set_path=True))
    extract(jar, "https://www.victim.test/a/", "session=value; Path=/a")
    extract(jar, "https://www.victim.test/b/", "session=x; Path=/a; Max-Age=0")
    assert len(jar) == 1
    extract(jar, "https://www.victim.test/a/", "session=x; Path=/a; Max-Age=0")
    assert len(jar) == 0


def test_expired_cookie_obeys_blocked_domain_policy():
    jar = CookieJar()
    extract(jar, "https://www.victim.test/", "session=value; Domain=.victim.test; Path=/")
    jar.set_policy(DefaultCookiePolicy(blocked_domains=[".victim.test"]))
    extract(jar, "https://www.victim.test/", "session=x; Domain=.victim.test; Path=/; Max-Age=0")
    assert len(jar) == 1
    jar.set_policy(DefaultCookiePolicy())
    extract(jar, "https://www.victim.test/", "session=x; Domain=.victim.test; Path=/; Max-Age=0")
    assert len(jar) == 0
