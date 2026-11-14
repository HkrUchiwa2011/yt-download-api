"""Regression checks for automated review gates."""

import copy
import json

from scripts.check_container_scan import assess
from scripts.check_native_updates import changes, digest, release_changes


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
