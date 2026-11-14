# Maintenance

## Automated checks

GitHub Actions runs on pull requests, pushes to `main`, manual dispatch, and
Mondays at 06:17 UTC. It tests Python 3.11/3.13 with isolated Redis, checks lint,
formatting and locked exports, audits Python packages, and runs the Docker media
and native security regressions. Tests use local media fixtures, not YouTube.

The runtime image is scanned with Trivy. Any critical finding, unreviewed high
package/advisory pair or detected secret fails the job. Reviewed high findings
remain visible in the complete `container-security-report` artifact; the gate
does not hide them or claim that their package versions are fixed. Medium, low
and unknown findings remain available for manual review. Reports are kept for
14 days.

`scripts/check_native_updates.py` also checks official FFmpeg/Expat/Python
releases, Debian source-package advisories and Expat's pending-security-issues
list. New advisories, reopened or changed open advisories, new releases and
changes to the pending list require review. This supplements the package scan;
it cannot detect every undisclosed vulnerability or assess applicability itself.

Dependabot proposes weekly updates for uv dependencies, GitHub Actions and Docker
images on Mondays at 06:00 UTC. Compatible Python updates are grouped; major
updates remain separate. Security updates may arrive outside that schedule.
There is no automatic merge, release, package publication or deployment.
Workflow jobs have read-only repository permissions and use pinned actions.

GitHub may disable scheduled workflows after 60 days without repository activity;
check that the schedule remains enabled during inactive periods.

## Reviewing a dependency pull request

1. Read the release notes and security advisories. Check API behavior and Python
   compatibility, not just the proposed version number.
2. Run `uv sync --locked` with the uv version pinned in CI.
3. Regenerate pip/Docker snapshots if `uv.lock` changed:

   ```bash
   uv run --locked python scripts/export_requirements.py
   ```

4. Commit the regenerated exports to the pull request. CI deliberately refuses
   stale exports; Dependabot's uv update alone may not regenerate these files.
5. Wait for all Python and container jobs to pass. Review the full security
   artifact and the native-watch output before merging.

## Native runtime changes

Python image updates must match `PYTHON_VERSION`, its source hash and the
extension location in Dockerfile. Review the cookie policy backport and remove
it only once the selected upstream version includes the fix. FFmpeg/Expat
updates need verified source hashes, patch review and the complete container
tests; see [build/README.md](build/README.md).

`security/container-reviewed.json` records the reviewed high package pairs and
hashes of the container/native configuration. Changing those files requires a
new assessment. `security/native-reviewed.json` records the source advisory
snapshot and reasons for open findings. Refresh either file only after reviewing
the changed exposure, then update `SECURITY_REVIEW.md`. Never accept new IDs or
replace fingerprints solely to make a failing job green.

Check actual YouTube extraction periodically with a short video you have the
right to download. Upstream blocking can change independently of package
versions; this manual check complements deterministic CI tests.

## Releases

Keep `CHANGELOG.md` current. Publish a version/tag only after reviewing green
checks and documenting migration steps. The client is released independently;
verify it against the API before publishing a new SDK version.
