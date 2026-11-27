# Local security review — 2026-11-13

## Follow-up — 2026-11-27

- The runtime installs Debian's patched libzstd1 for CVE-2026-124851 and retains the patched zlib1g for CVE-2026-85091.
- FFmpeg 9.1 incorporates the earlier encryption-list, HDR, AAC, AV1, Vorbis and VP9 backports and covers new advisories in enabled HEVC paths. The restricted build and per-file PSSH limit are preserved.
- Expat 2.11.0 fixes CVE-2026-124317, CVE-2026-128241 and CVE-2026-134703. The same CPython interpreter and HTTP backports remain in use.
- Trivy reports CVE-2026-107494 and CVE-2026-124709 for three Debian OpenSSL packages. Both require OpenSSL's QUIC stack. The supplied API serves HTTP/1.1 over TCP and its clients do not use OpenSSL QUIC. Both findings remain visible in the full scan. An external HTTP/3 reverse proxy has a separate security scope.
- The [native advisory triage](security/native-triage-2026-11-27.md) records the individual applicability assessments and the remaining upstream issues.

## Follow-up — 2026-11-18

- Monday's scheduled native watch correctly required review of 87 new FFmpeg IDs and three Python 3.13 IDs. This follow-up assesses them individually; [the triage table](security/native-triage-2026-11-18.md) records affected components and treatment.
- The supplied Docker Python library backports CVE-2026-103995's HTTP framing validation and its optional-whitespace compatibility follow-up. Invalid signed, prefixed or underscored chunk sizes and Content-Length values no longer determine response framing. Valid Content-Length whitespace remains supported on persistent connections.
- FFmpeg 9.0.2-yt2 backports CVE-2026-125205 (AV1 OBU limits), CVE-2026-125223 (VP9 error cleanup), CVE-2026-125224 (one-time Vorbis parsing), CVE-2026-125225 (AAC bit-reader bounds) and CVE-2026-125253 (VP9 superframe arithmetic). Unused FLAC decoder/parser/demuxer components are removed for CVE-2026-125221. The supplied image remains focused on YouTube media, with WAV/PCM fixtures supported.
- Other new FFmpeg entries concern omitted decoders, encoders, hardware acceleration or bitstream-filter operations; some also have fixes in 9.0.2. Ordinary MP3 decoding differs from the omitted `mp3adu` API path. Enabled H.264/HEVC stream-copy filters do not invoke `h264_metadata` SEI insertion. Re-enabling these components requires reassessment.
- Python's IMAP STARTTLS issue (CVE-2026-115559) concerns an unused protocol. The Morsel attribute-injection issue (CVE-2026-16052) requires control of emitted response-cookie attributes; the application does not create such cookies from API input. These runtime versions are not certified fixed for unrelated uses.
- Refreshed Python dependency audits report zero known advisories (69 API and 41 SDK records). No SDK code or dependency changes are required by this review. Installations outside the supplied image, including SDK interpreters, manage their own Python/native runtime updates.
- The new runtime Trivy scan remains at **0 critical, 47 high, 92 medium, 65 low and 20 unknown package/advisory pairs**, with no Python-package advisories or secrets. All pairs match Wednesday's earlier scan. The existing high-package applicability assessment remains valid: build changes remove unused processing and backport fixes without enabling new protocols, tools or privileges. Source-built libraries and Python standard-library fixes still require the separate source review.
- Container/native fingerprints are refreshed after this assessment. The gate now also rejects native patch additions and removals, so an unlisted patch cannot silently reuse an older review.
- Verification: **120 Docker API/native/media tests**, **80 non-media API tests on each of Python 3.11 and 3.13**, and **45 SDK tests on each version** pass. AAC, AV1 and Vorbis native regressions fail against the previous supplied FFmpeg and pass against the patched library. The compiled inventory confirms FLAC, `mp3adu`, Blu-ray LPCM, JPEG-processing filters and hardware acceleration are absent. Lint, formatting, locked exports, the runtime scan gate and a fresh online native-source watch pass. The corrected runtime also extracts the existing Big Buck Bunny video's metadata (635 seconds, 57 advertised formats); this check downloads no media. No running service was replaced.

## Follow-up — 2026-11-14

- Python dependency audits still report no known vulnerabilities (69 API and 41 SDK records). FastAPI's corrective 0.162.7 update is locked and exported.
- New CVE-2026-124249 affects Python's cookie expiration policy. The supplied Docker library now includes the upstream 3.13 backport, with cross-domain, path and blocklist regression coverage. It is not yet fixed in the selected base release.
- New CVE-2026-115791 concerns archive-extraction command-line tools, which API routes do not invoke. CVE-2026-128241 affects `xmlwf`, excluded from our Expat build. A new unknown-severity dpkg source-package unpacking alert, CVE-2026-91094, does not concern runtime API operations or binary-package installation.
- The refreshed runtime scan remains at zero critical, 47 high, 89 medium and 65 low pairs; unknown pairs increase to five. All alerts remain visible. Source-built components continue to receive separate review.
- Updated verification: 91 tests in the Docker API/native suite, 76 non-media tests on Python 3.11 and 3.13 with Redis, and 45 SDK tests on both Python versions. Workflow lint, Dependabot schema validation and lock/export consistency checks pass.
- Automated checks and the weekly source/advisory watch are described in [MAINTENANCE.md](MAINTENANCE.md). Reviewed configuration fingerprints prevent silently reusing the package assessment after changing native/container assumptions.

## Outcome

Application fixes and local verification cover both the API and SDK. The supplied
Docker image now uses a restricted FFmpeg 9.0.2 with targeted encryption/HDR
fixes, and Expat 2.10.0 for Python's XML parser. libxml2 and the broad Debian
multimedia stack are absent. The remaining package alerts are assessed below;
none are suppressed. This review concerns the supplied configuration, not every
environment in which an open-source user may choose to install the application.
It is not a guarantee that all vulnerabilities, including undisclosed ones, are absent.

## Application changes reviewed

- Required API key, known placeholder rejection, constant-time comparison, separate failed-authentication rate limit and secret-safe configuration/errors/logs.
- Canonical HTTPS YouTube URLs on exact supported hosts, single video IDs, no playlists, common validation for `/info` and downloads, and worker-side revalidation.
- Webhooks disabled by default; exact public HTTPS allowlist, required HMAC secret, public-only DNS validation, IP pinning with original TLS hostname verification, no redirects/environment proxies, bounded delivery retries and no local paths in payloads.
- Redis-backed JSON jobs and atomic shared admission/disk reservations. Initial status and queue entry commit together. Metadata, sockets, downloads, request bodies and FFmpeg output sizes are bounded. Files survive a late callback/worker failure after download completion.
- UUID-only routes, exact recorded output names, service-owned private directories, no-follow file descriptors, streaming handle cleanup, repeat retrieval, explicit deletion and expiration cleanup that preserves active downloads.
- Current locked Python dependencies with package hashes; pinned Python base, native source hashes and patched runtime libraries. Runtime dependency installers are removed. Docker runs as UID 10001 with read-only root filesystems, no additional capabilities, private Redis and memory/process limits in Compose.

## Verification

- Full Docker suite: **83 API/security/integration tests**, including real local yt-dlp transfers and FFmpeg MP4/MP3/WebM processing, FFmpeg output-size rejection, concurrency, lifecycle, SSRF and file-access regressions.
- A pending job survived an actual Compose API container recreation with its worker stopped; cancellation then released its admission slot. A forked worker timeout is covered by a regression test.
- SDK: **45 tests** on Python 3.13 and 3.11; API tests also exercised on Python 3.11 (media cases require FFmpeg).
- Static security/lint checks, formatting checks, hash-locked installations and SDK wheel/sdist builds.
- `pip-audit`: no known advisories in the resolved Python environments. The final container Python package scan likewise has no findings. This does not assess future advisories or unknown vulnerabilities.
- Actual HTTP API/SDK smoke: metadata extraction for two existing videos; a Creative Commons Big Buck Bunny audio download produced **15,232,463 bytes**, two retrievals matched byte-for-byte, and explicit deletion succeeded. The old `BaW_jenozKc` example video is unavailable upstream; local media fixtures do not depend on its availability.
- After native-stack replacement, the running Compose API/SDK downloaded the same video as MP4 (**46,283,921 bytes**), MP3 (**15,232,463 bytes**) and WebM (**34,312,454 bytes**). Production ffprobe confirmed the expected audio/video streams. Each format was retrieved twice with identical SHA-256 and then deleted. A local MPEG-TS-to-MP4 stream-copy check also passed.
- Final container filesystem scanned with Trivy 0.76 against its vulnerability database downloaded on the review date. No secrets detected. Package/image inventories were checked against installed distribution metadata; the earlier Python findings came from pip's bundled dependency inventory and disappear when the unnecessary runtime installer is removed.

## Infrastructure boundaries

Redis and the shared download directory are trusted. RQ's JSON serializer avoids pickle deserialization; it does not make write access to Redis safe. Redis must remain private. All callers using the same API key share all jobs; this application does not implement tenant isolation.

The Compose API is bound to localhost. Remote access needs an HTTPS reverse proxy with connection/request limits. Forwarded client-IP headers are not trusted by the supplied server. Container limits mitigate resource exhaustion and media-processing faults; they do not eliminate native-library vulnerabilities. The Render blueprint was reviewed as configuration, but no remote deployment or disk-permission verification was performed.

Pending jobs survive API restarts while their queue TTL remains valid. Interrupted running jobs are failed by RQ maintenance rather than resumed. File responses support a single HTTP byte range with If-Range checks. Multiple ranges are refused. The Python client does not implement partial-transfer resume.

## Container and native component review

The initial Debian FFmpeg image reported **1 critical, 281 high, 386 medium,
201 low and 30 unknown package/advisory pairs**. libxml2 caused the critical
CVE-2026-6653 finding. Debian stable has not published a fixed package for that
snapshot; this does not imply there are no upstream fixes. Debian marks this
specific issue `no-dsa`/minor, while Trivy uses a critical vendor severity.
Removing libxml2 from the supplied image removes this component and finding.

The revised runtime package scan reports **0 critical, 47 high, 89 medium,
65 low and 4 unknown pairs**, and no Python-package advisories or secrets.
The 47 high pairs represent **11 distinct IDs**, not 47 independent flaws.
The installed base packages are still flagged; the review does not mark their
package versions fixed merely because their affected functions are unused.

Trivy does not reliably inventory our source-built FFmpeg or Python's embedded
XML parser. They were assessed separately. Of the original **44 FFmpeg advisory
IDs**, 33 have fixes in the newer release line, nine concern components omitted
from this build, and two need additional targeted patches. We checked the Debian
security tracker and upstream references rather than treating missing scan
results as proof of remediation. Details and source provenance are in
[build/README.md](build/README.md).

| Native finding | Treatment in the supplied image |
|---|---|
| CVE-2026-107678 | Iterative encryption-list release plus a 64-record PSSH limit bounds the MOV append path. Native tests free 100,000 records under a 128 KiB stack; a crafted MP4 with excessive metadata is rejected. |
| CVE-2026-107676 | Backported upstream HDR serialization fix; saturation metadata round-trip verified when tone mapping is absent. |
| CVE-2026-107675, CVE-2026-107677, CVE-2026-107696, CVE-2026-120210 | SFTP, DASH, RTSP and IMF implementations omitted. FFmpeg exposes only local file/pipe protocols. |
| CVE-2026-120243 through CVE-2026-120247 | Go2Meeting, PCX, Sun Raster, CDXL and Huffyuv decoders omitted. |
| CVE-2026-113351, CVE-2026-115506, CVE-2026-117610, CVE-2026-118370 | Expat 2.10.0 includes these fixes. CPython's matching pyexpat extension is rebuilt against that shared library; ElementTree uses the same C API. |

Upstream Expat's [issue 1160](https://github.com/libexpat/libexpat/issues/1160)
tracks additional undisclosed/pending issues. Their applicability cannot be
established from public details. XML metadata processing remains a bounded child
process; worker/container limits provide containment, not proof of immunity.

### Remaining high package alerts

| Advisory IDs | Component/function | Applicability to the supplied API/Compose configuration |
|---|---|---|
| CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 | util-linux privileged mount hooks/nsenter | No API route invokes mount, nsenter or login. Services run as UID 10001, without capabilities and with no-new-privileges. An administrator using these tools in another environment has a different exposure. |
| CVE-2025-69720 | ncurses `infocmp` analyzer | The tool is present in the base image but never invoked by the application. The vulnerable analyzer is not terminal-library usage. |
| CVE-2026-54369 | libacl pathname ACL helpers | Application file operations use Python descriptors, not privileged libacl pathname operations. No ACL utility is exposed through the API. |
| CVE-2026-119373, CVE-2026-119374, CVE-2026-119379 | SQLite FTS5/session operations | No database upload, SQL execution, FTS index or changeset operation. Jobs use Redis; yt-dlp caching is disabled and browser-cookie import is not configured. |
| CVE-2026-16742 | systemd-homed | Service is absent and not running; installed libsystemd/libudev records inherit the source-package alert. |
| CVE-2026-9538 | Perl Archive::Tar | No Perl archive processing in the application. |

### Other package alerts and limits

Remaining medium/low/unknown alerts cover base OS utilities and libraries. The
reviewed medium descriptions concern privileged/local tools; SQL/database input;
C++ APIs; glibc `wordexp`, monetary formatting, special `fopen` mode strings,
legacy DNS *printing* functions, uncommon iconv conversions, locale catalogs,
setuid loaders and nscd; and OpenSSL CMS, QUIC or AES-GCM-SIV APIs. These are
not the application's ordinary Python DNS resolution/TLS/file operations.
No nscd or systemd service runs in the supplied runtime. Archives are not
uploaded or extracted by API routes.

CVE-2026-8674 is a glibc resolver failure caused by oversized DNS search domains
in host resolver configuration or `LOCALDOMAIN`. This is an operator/network
configuration boundary, not an API parameter. Keep container DNS/search-domain
configuration trusted; an administrator choosing a different environment must
assess it there. Unknown-severity and historical low findings are retained in
scan results rather than certified harmless.

Changing native build flags, enabling new input formats, adding browser-cookie
imports/SQL/Perl processing, granting container privileges, or deploying with a
different base image requires a new applicability review. No remote deployment
was performed; automated checks are described in [MAINTENANCE.md](MAINTENANCE.md).
