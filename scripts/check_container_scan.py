"""Report all findings and reject unreviewed high/critical alerts or secrets."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assess(report, reviewed):
    known = {(item["id"], item["package"]) for item in reviewed["findings"]}
    counts = Counter()
    new = set()
    secrets = 0
    for result in report.get("Results", []):
        secrets += len(result.get("Secrets", []))
        for finding in result.get("Vulnerabilities", []):
            severity = finding["Severity"]
            counts[severity] += 1
            pair = (finding["VulnerabilityID"], finding["PkgName"])
            if severity == "CRITICAL" or (severity == "HIGH" and pair not in known):
                new.add(pair)
    return counts, sorted(new), secrets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    reviewed = json.loads((ROOT / "security/container-reviewed.json").read_text())
    if report.get("SchemaVersion") != 2 or not report.get("Results"):
        raise ValueError("Missing or unsupported Trivy report")
    for filename, expected in reviewed["configuration_sha256"].items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Container review must be refreshed after changing {filename}")
    counts, new, secrets = assess(report, reviewed)
    print("Container scan: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"Secrets: {secrets}; unreviewed high/critical package pairs: {len(new)}")
    print("Existing reviewed findings remain visible in the full scan artifact.")
    for identifier, package in new:
        print(f"Review required: {identifier} ({package})")
    return int(bool(new or secrets))


if __name__ == "__main__":
    raise SystemExit(main())
