"""Cookie policy regressions for the Python library shipped in Docker."""

import os
from email.message import Message
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.request import Request

import pytest


class CookieResponse:
    def __init__(self, header):
        self.headers = Message()
        self.headers["Set-Cookie"] = header

    def info(self):
        return self.headers


def extract(jar, host, header):
    jar.extract_cookies(CookieResponse(header), Request(host))  # noqa: S310 - metadata only, no I/O


@pytest.mark.skipif(
    not os.getenv("PATCHED_PYTHON_RUNTIME"), reason="Requires patched Docker Python"
)
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


@pytest.mark.skipif(
    not os.getenv("PATCHED_PYTHON_RUNTIME"), reason="Requires patched Docker Python"
)
def test_expired_cookie_obeys_path_policy():
    jar = CookieJar(DefaultCookiePolicy(strict_ns_set_path=True))
    extract(jar, "https://www.victim.test/a/", "session=value; Path=/a")
    extract(jar, "https://www.victim.test/b/", "session=x; Path=/a; Max-Age=0")
    assert len(jar) == 1
    extract(jar, "https://www.victim.test/a/", "session=x; Path=/a; Max-Age=0")
    assert len(jar) == 0


@pytest.mark.skipif(
    not os.getenv("PATCHED_PYTHON_RUNTIME"), reason="Requires patched Docker Python"
)
def test_expired_cookie_obeys_blocked_domain_policy():
    jar = CookieJar()
    extract(jar, "https://www.victim.test/", "session=value; Domain=.victim.test; Path=/")
    jar.set_policy(DefaultCookiePolicy(blocked_domains=[".victim.test"]))
    extract(jar, "https://www.victim.test/", "session=x; Domain=.victim.test; Path=/; Max-Age=0")
    assert len(jar) == 1
    jar.set_policy(DefaultCookiePolicy())
    extract(jar, "https://www.victim.test/", "session=x; Domain=.victim.test; Path=/; Max-Age=0")
    assert len(jar) == 0
