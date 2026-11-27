# Changelog

## 1.1.0 — unreleased

- GitHub Actions regression/security checks and weekly Dependabot proposals; explicit review gates for container/native advisories.
- Authenticate native-watch GitHub API requests with the temporary read-only job token; keep credentials off other source hosts and refuse redirects.
- FastAPI 0.162.7 and a Python cookie-policy backport for CVE-2026-124249.
- Python HTTP framing validation for CVE-2026-103995, preserving valid Content-Length whitespace.
- Restricted FFmpeg 9.1 includes the previous native security backports. The local PSSH cap and exclusion of unused FLAC components remain in place. Expat 2.11.0 adds XML parser security fixes.
- Redis-backed JSON job queue and supervised/separate workers; atomic global capacity and disk reservations.
- Strict YouTube URLs, restricted signed DNS-pinned HTTPS webhooks and bounded request/metadata processing.
- Exact UUID file lookup, private directories, symlink-safe streaming, repeat retrieval and TTL cleanup.
- Separate polling/authentication budgets, constant-time API key checks and sanitized errors/logs.
- Current locked yt-dlp/EJS/Deno dependencies; pinned Python image; non-root Docker services.
- Accurate Compose, Render and usage documentation; local regression and integration tests.

### Migration from 1.0

Use a generated API_KEY of at least 32 characters. Deploy the worker as well as the API, with the same Redis namespace and download filesystem. Stop accepting work in the old deployment and let existing downloads finish before upgrading: the old Redis keys and flat temporary files are not migrated.

Files are retained until TTL or DELETE rather than deleted after GET. Webhooks require an explicit public-host allowlist and signing secret. HTTP video/webhook URLs, malformed video IDs and audio_only with a non-MP3 format are refused. Interactive docs require ENABLE_DOCS=true. The Render blueprint now needs paid resources; review it before deployment.
