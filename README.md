# yt-download-api

[English](README.md) | [Français](README.fr.md)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

A self-hosted YouTube download API built with FastAPI, yt-dlp, FFmpeg and Redis.
Submit a video, poll its status and retrieve the file. The HTTP endpoints remain compatible with the Python [yt-download-client](https://github.com/HkrUchiwa2011/yt-download-client).

## Run with Docker Compose

```bash
git clone https://github.com/HkrUchiwa2011/yt-download-api.git
cd yt-download-api
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Put the generated secret in `.env` as `API_KEY`. The placeholder is rejected at startup. Then:

```bash
docker compose up --build -d
```

The supplied image builds a restricted FFmpeg 9.0.2 with targeted security
patches and updates Python's embedded XML parser. Sources are pinned by hash;
compiler stages are excluded from the runtime. See [native build details](build/README.md).

The API listens at **http://127.0.0.1:8000**. Redis is internal to Compose; no Redis port is published. The API and worker share a download volume, and Redis uses persistent append-only storage. To run additional workers:

```bash
docker compose up -d --scale worker=3
```

`MAX_CONCURRENT_DOWNLOADS` caps all admitted jobs, including jobs waiting for a worker, across API processes. A full service returns `503` and `Retry-After`; it does not create a job. Disk space is reserved conservatively for admitted downloads and their post-processing.

Expose the API through an HTTPS reverse proxy when accessing it remotely. The supplied listener binds to localhost. Forwarded IP headers are deliberately ignored; clients behind a proxy share its IP budget. Adjust IP limits for that deployment rather than trusting arbitrary forwarded headers.

## Run without Docker

Install Python 3.11+, Redis, FFmpeg/ffprobe and [uv](https://docs.astral.sh/uv/). Python dependencies, including Deno and yt-dlp's EJS component, are locked in `uv.lock`. Outside Docker, use current security-patched native packages supplied by your environment; the container review does not certify a different installation.

```bash
uv sync --locked --no-dev
uv run --locked --no-dev python -m app.server
```

The server starts the API and one supervised worker. For separate processes sharing the **same filesystem**, set `EMBEDDED_WORKERS=0` and run:

```bash
uv run --locked --no-dev python -m app.worker
uv run --locked --no-dev python -m app.server
```

Alternatively, `pip install --require-hashes -r requirements.txt` installs the locked runtime dependencies. `requirements.txt` is generated from `uv.lock`.

## HTTP API

All routes except `/health` require `X-API-Key`. Missing or incorrect keys return `401`.

| Method | Route | Behavior |
|---|---|---|
| GET | `/health` | Checks Redis and registered workers; returns 503 if unavailable |
| GET | `/info?url=...` | Video metadata, with a bounded extraction process |
| POST | `/download` | Durably queues a download and returns its UUID |
| GET | `/status/{job_id}` | Job status; independent polling rate budget |
| GET | `/file/{job_id}` | Retrieves a completed file without deleting it |
| DELETE | `/file/{job_id}` | Deletes a completed file; active jobs return 409 |

Supported formats: `mp4`, `mp3`, `webm`. Qualities: `best`, `1080p`, `720p`, `480p`, `360p`, `audio_only`. MP3 always selects audio streams; `audio_only` requires MP3. MP4 and WebM select streams compatible with the requested container. If compatible streams are unavailable, the job fails rather than silently returning another format.

Video URLs must use HTTPS and a supported YouTube hostname with an 11-character video ID. Watch, short, embed and live URL forms are canonicalized to a single watch URL. Playlist and arbitrary query parameters are removed. Live downloads and videos with unknown duration are refused; `/info` can return `duration: null`.

```bash
curl --fail http://localhost:8000/download \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"url":"https://youtu.be/aqz-KE-bpKQ","format":"mp4","quality":"720p"}'
```

The response contains `job_id`, `status: "pending"` and a message. Its initial state and queue entry are committed together. Status follows `pending` → `started` → `progress` → `post_processing` → `success` / `failure`.

Files remain available for `FILE_TTL_MINUTES` after completion, unless explicitly deleted. Expired files are cleaned every minute. A client that disconnects can fetch the file again. Single HTTP byte ranges and If-Range are supported for clients that implement resume; multiple ranges are refused. Pending jobs survive API/worker restarts while their queue TTL remains valid. Interrupted running jobs fail; partially downloaded bytes are not resumed automatically. RQ marks abandoned work during its periodic maintenance, so detection after an abrupt worker crash is not instantaneous.

## Python client

```python
from yt_download_client import YTDownloadClient

with YTDownloadClient("http://localhost:8000", api_key="YOUR_KEY") as client:
    path = client.download("https://youtu.be/aqz-KE-bpKQ", format="mp4", quality="720p")
```

The client handles polling and bounded retries for safe GET operations. Submission is never automatically retried, avoiding duplicate jobs.

## Webhooks

Webhooks are disabled by default. Configure both:

```dotenv
WEBHOOK_ALLOWED_HOSTS=["callbacks.example.org"]
WEBHOOK_SECRET=YOUR_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS
```

Submit `webhook_url: "https://callbacks.example.org/download-finished"`. Only exact allowed hosts on HTTPS port 443 are accepted. DNS must resolve exclusively to public IPs. Connections are pinned to a validated IP while verifying the original hostname's TLS certificate; redirects and environment proxies are disabled. Network errors and HTTP 5xx responses receive at most three delivery attempts. Delivery failure does not change the completed download's status.

The callback contains `job_id`, `status` and public result/error fields. It contains no local filename or filesystem path. Verify the `X-YT-Signature` header as `sha256=` followed by HMAC-SHA256 of `timestamp + "." + raw_request_body`, using `WEBHOOK_SECRET`. The timestamp is in `X-YT-Timestamp`. Compare signatures in constant time and reject old timestamps and duplicate deliveries on the receiver.

## Configuration

All values are environment variables; see `.env.example`.

| Variable | Default | Meaning |
|---|---|---|
| `API_KEY` | required | Random secret, at least 32 characters |
| `REDIS_URL` | `redis://localhost:6379/0` | Private Redis connection; use TLS for remote Redis |
| `REDIS_NAMESPACE` | `yt` | Isolates jobs and rate counters for this deployment |
| `TMP_DIR` | `/tmp/yt-downloads` | Dedicated directory owned by the service user |
| `FILE_TTL_MINUTES` | 30 | File and terminal-state retention |
| `MAX_DURATION_SECONDS` | 3600 | Maximum known video duration |
| `MAX_FILESIZE_MB` | 500 | Maximum combined source size and final file size |
| `MIN_FREE_SPACE_MB` | 256 | Storage safety margin |
| `JOB_TIMEOUT_SECONDS` | 900 | Queue TTL and worker execution deadline, separately |
| `SOCKET_TIMEOUT_SECONDS` | 15 | Network timeout; metadata deadline is three times this value |
| `MAX_CONCURRENT_DOWNLOADS` | 5 | Global admitted download cap |
| `MAX_CONCURRENT_INFO_REQUESTS` | 2 | Global metadata extraction cap |
| `RATE_LIMIT_PER_MINUTE_IP` / `RATE_LIMIT_PER_MINUTE_KEY` | 10 / 30 | Work request budgets |
| `STATUS_RATE_LIMIT_PER_MINUTE_IP` / `STATUS_RATE_LIMIT_PER_MINUTE_KEY` | 120 / 300 | Separate polling budgets |
| `EMBEDDED_WORKERS` | 1 | Workers supervised by `app.server`; Compose overrides this to zero |
| `ENABLE_DOCS` | false | Enables `/docs` and `/openapi.json` |
| `PROXY_URL` | empty | Operator-configured yt-dlp proxy; keep credentials secret |
| `WEBHOOK_ALLOWED_HOSTS` / `WEBHOOK_SECRET` | disabled | Callback allowlist and HMAC secret |

Redis and the shared download directory are trusted infrastructure. All callers using the single API key can access all jobs; this API does not provide user accounts or tenant isolation. Do not expose Redis or the download volume publicly. Host-level egress controls provide additional isolation for yt-dlp/FFmpeg and any operator-configured proxy. YouTube may still reject datacenter IPs even when extraction dependencies are current.

## Render

`render.yaml` uses a paid web service with a persistent disk and a paid Key Value service. It starts a supervised worker in the web service because separate Render services cannot share this disk. The blueprint defaults to 100 MB files and two admitted jobs. Check current Render availability, pricing and disk ownership before deploying. No deployment is performed by local tests. The original free blueprint did not provide durable file storage.

## Local checks

Use an isolated test Redis; tests clean only their own namespaced data:

```bash
docker run --rm -p 127.0.0.1:16379:6379 redis:8-alpine
# In a second terminal:
uv sync --locked
TEST_REDIS_URL=redis://127.0.0.1:16379/15 uv run --locked pytest
uv run --locked ruff check app tests
uv run --locked ruff format --check app tests
uv run --locked pip-audit
```

Media integration tests additionally need FFmpeg/ffprobe. The Docker `tests`
target also checks the patched production native libraries; see
[native build details](build/README.md) for its commands. Without `TEST_REDIS_URL`,
Redis integration tests are explicitly skipped; URL/security unit tests still run.
See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for the local review scope and results,
and [CHANGELOG.md](CHANGELOG.md) for migration notes.

## License

[MIT](LICENSE) for application code. Bundled FFmpeg, Expat and other components
retain their own licenses; see [native build details](build/README.md).
Download only content you have the right to download.
