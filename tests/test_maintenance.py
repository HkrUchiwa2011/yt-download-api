"""Regression checks for automated review gates."""

import copy
import hashlib
import json

import httpx
import pytest

from scripts.check_container_scan import assess, check_configuration, configuration_files
from scripts.check_native_updates import changes, digest, fetch, release_changes


@pytest.mark.parametrize("change", ["add", "remove", "modify"])
def test_container_gate_rejects_unreviewed_patch_inventory_changes(tmp_path, change):
    directory = tmp_path / "build/python-patches"
    directory.mkdir(parents=True)
    patch = directory / "reviewed.patch"
    patch.write_text("reviewed fix")
    for name in ("Dockerfile", "compose.yaml", "build/build-ffmpeg.sh", "build/build-pyexpat.sh"):
        (tmp_path / name).write_text("reviewed configuration")
    baseline = {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in configuration_files(tmp_path)
    }
    check_configuration(tmp_path, baseline)
    if change == "add":
        (directory / "new.patch").write_text("unreviewed fix")
    elif change == "remove":
        patch.unlink()
    else:
        patch.write_text("changed fix")
    with pytest.raises(ValueError, match="review must be refreshed"):
        check_configuration(tmp_path, baseline)


def test_container_gate_keeps_reviewed_high_alerts_visible():
    finding = {"VulnerabilityID": "CVE-2026-1234", "PkgName": "base-library", "Severity": "HIGH"}
    report = {"Results": [{"Vulnerabilities": [finding]}]}
    baseline = {"findings": [{"id": "CVE-2026-1234", "package": "base-library"}]}
    counts, new, secrets = assess(report, baseline)
    assert counts["HIGH"] == 1
    assert new == []
    assert secrets == 0
    finding["Severity"] = "CRITICAL"
    assert assess(report, baseline)[1] == [("CVE-2026-1234", "base-library")]


def test_container_gate_rejects_new_package_pairs_and_secrets():
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-1234",
                        "PkgName": "another-library",
                        "Severity": "HIGH",
                    }
                ],
                "Secrets": [{"RuleID": "test-secret"}],
            }
        ]
    }
    baseline = {"findings": [{"id": "CVE-2026-1234", "package": "base-library"}]}
    _, new, secrets = assess(report, baseline)
    assert new == [("CVE-2026-1234", "another-library")]
    assert secrets == 1


def test_native_gate_detects_new_changed_and_reopened_advisories():
    entry = {"description": "Reviewed condition", "releases": {"sid": {"status": "open"}}}
    data = {"ffmpeg": {"CVE-known": entry}}
    baseline = {
        "packages": {
            "ffmpeg": {
                "known_ids": ["CVE-known", "CVE-closed"],
                "open": {"CVE-known": {"description_sha256": digest(entry["description"])}},
            }
        }
    }
    assert changes(data, baseline) == []
    changed = copy.deepcopy(data)
    changed["ffmpeg"]["CVE-known"]["description"] = "New affected condition"
    changed["ffmpeg"]["CVE-new"] = entry
    changed["ffmpeg"]["CVE-closed"] = entry
    problems = changes(changed, baseline)
    assert "Changed advisory: ffmpeg CVE-known" in problems
    assert "New advisory: ffmpeg CVE-new" in problems
    assert "Unreviewed open advisory: ffmpeg CVE-closed" in problems


def test_native_release_watch_uses_the_configured_python_series():
    baseline = {"versions": {"ffmpeg": "9.0.2", "expat": "2.10.0", "python": "3.13.18"}}
    ffmpeg = 'href="ffmpeg-9.0.2.tar.xz"'
    expat = json.dumps({"tag_name": "R_2_10_0"})
    index = '<a href="3.13.18/">old</a><a href="3.14.5/">other series</a>'
    assert release_changes(baseline, ffmpeg, expat, index) == []
    index += '<a href="3.13.19/">new</a>'
    assert release_changes(baseline, ffmpeg, expat, index) == [
        "New python release: 3.13.18 -> 3.13.19"
    ]


def test_native_feed_limits_are_configurable_and_enforced(httpx_mock):
    url = "https://metadata.test/feed"
    httpx_mock.add_response(url=url, content=b"12345", is_reusable=True)
    assert fetch(url, max_bytes=5) == "12345"
    with pytest.raises(ValueError, match="size limit"):
        fetch(url, max_bytes=4)


def test_native_github_fetch_uses_job_token(monkeypatch, httpx_mock):
    monkeypatch.setenv("GITHUB_TOKEN", "test-job-token")
    url = "https://api.github.com/repos/libexpat/libexpat/releases/latest"
    httpx_mock.add_response(
        url=url, match_headers={"Authorization": "Bearer test-job-token"}, text="metadata"
    )
    assert fetch(url) == "metadata"


def test_native_fetch_without_job_token_is_anonymous(monkeypatch, httpx_mock):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    url = "https://api.github.com/repos/libexpat/libexpat/releases/latest"
    httpx_mock.add_response(url=url, text="metadata")
    assert fetch(url) == "metadata"
    assert "authorization" not in httpx_mock.get_request().headers


@pytest.mark.parametrize(
    "url",
    [
        "https://metadata.test/feed",
        "https://api.github.com.attacker.test/feed",
        "http://api.github.com/feed",
        "https://api.github.com:8443/feed",
    ],
)
def test_native_fetch_keeps_token_off_other_origins(monkeypatch, httpx_mock, url):
    monkeypatch.setenv("GITHUB_TOKEN", "test-job-token")
    httpx_mock.add_response(url=url, text="metadata")
    assert fetch(url) == "metadata"
    assert "authorization" not in httpx_mock.get_request().headers


def test_native_authenticated_fetch_refuses_redirects(monkeypatch, httpx_mock):
    monkeypatch.setenv("GITHUB_TOKEN", "test-job-token")
    url = "https://api.github.com/repos/libexpat/libexpat/releases/latest"
    httpx_mock.add_response(
        url=url,
        status_code=302,
        headers={"Location": "https://metadata.test/redirect"},
        match_headers={"Authorization": "Bearer test-job-token"},
    )
    with pytest.raises(httpx.HTTPStatusError):
        fetch(url)
    assert len(httpx_mock.get_requests()) == 1
