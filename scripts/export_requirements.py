"""Keep pip/Docker exports aligned with the reviewed uv lockfile."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = {"requirements.txt": ["--no-dev"], "requirements-dev.txt": ["--only-group", "dev"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for filename, groups in EXPORTS.items():
        result = subprocess.run(  # noqa: S603 - fixed uv command, no shell
            ["uv", "export", "--locked", "--no-header", *groups],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        target = ROOT / filename
        if args.check:
            if target.read_bytes() != result:
                stale.append(filename)
        else:
            target.write_bytes(result)
    if stale:
        print("Stale exports: " + ", ".join(stale))
        print("Run: uv run --locked python scripts/export_requirements.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
