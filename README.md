# yt-download-api

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

A self-hostable REST API to download YouTube videos. Built with FastAPI and yt-dlp.

Integrate it into your Discord bots, Telegram bots, automation scripts, or any HTTP client. Submit a job, poll for the status, grab the file — that's it.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/HkrUchiwa2011/yt-download-api)

---

## Features

- Download videos as `mp4`, `mp3`, or `webm`
- Quality selection: `best`, `1080p`, `720p`, `480p`, `360p`, `audio_only`
- `/info` endpoint — fetch title, duration, and available formats before downloading
- Webhook support — get notified when a job finishes instead of polling
- Rate limiting per IP and per API key
- Concurrent download cap to keep the server stable
- Auto-cleanup of downloaded files after 30 minutes
- Redis-backed job state

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/health` | Service health and active download count |
| `GET` | `/info?url=...` | Video metadata and available formats |
| `POST` | `/download` | Submit a download job |
| `GET` | `/status/{job_id}` | Poll job status |
| `GET` | `/file/{job_id}` | Download the output file |
| `DELETE` | `/file/{job_id}` | Delete a file manually |

All endpoints except `/health` require the `X-API-Key` header.

Interactive docs available at `/docs`.

---

## Quick start

### Requirements

- Docker + Docker Compose
- Or: Python 3.11+ and a running Redis instance

### Run locally

```bash
git clone https://github.com/HkrUchiwa2011/yt-download-api.git
cd yt-download-api
cp .env.example .env
```

Open `.env` and set a strong `API_KEY`. The other defaults work fine for local use.

```bash
docker compose up
```

The API will be available at `http://localhost:8000`.

<details>
<summary>Docker Compose file</summary>

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]
    volumes: [.:/app]
```

</details>

### Without Docker

```bash
pip install -r requirements.txt
redis-server &
uvicorn app.main:app --reload
```

---

## Deploy to Render

Click the deploy button at the top, or:

1. Fork this repo
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your fork
4. Render reads `render.yaml` and creates the web service + Redis automatically
5. Find your `API_KEY` under the service's **Environment** tab

---

## Usage

### Submit a download

```bash
curl -X POST https://your-api.onrender.com/download \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/dQw4w9WgXcQ", "format": "mp4", "quality": "720p"}'
```

```json
{
  "job_id": "abc-123",
  "status": "pending",
  "message": "Job queued. Poll status at GET /status/abc-123"
}
```

### Poll status

```bash
curl https://your-api.onrender.com/status/abc-123 \
  -H "X-API-Key: YOUR_KEY"
```

Status flow: `pending` → `started` → `progress` → `post_processing` → `success` / `failure`

### Download the file

```bash
curl -L https://your-api.onrender.com/file/abc-123 \
  -H "X-API-Key: YOUR_KEY" \
  -o video.mp4
```

### Get video info

```bash
curl "https://your-api.onrender.com/info?url=https://youtu.be/dQw4w9WgXcQ" \
  -H "X-API-Key: YOUR_KEY"
```

### With a webhook

Pass a `webhook_url` in your download request and the API will POST the result to it when the job finishes — no polling needed.

```json
{
  "url": "https://youtu.be/dQw4w9WgXcQ",
  "format": "mp3",
  "quality": "audio_only",
  "webhook_url": "https://your-server.com/callback"
}
```

---

## Use in your scripts

The API is designed to be scripted. Here's the full flow in a few languages.

### Python (recommended) — yt-download-client

The easiest way to use this API from Python is the official client, published on PyPI.

```bash
pip install yt-download-client
```

```python
from yt_download_client import YTDownloadClient

client = YTDownloadClient(
    base_url="https://your-api.onrender.com",
    api_key="YOUR_KEY",
)

path = client.download("https://youtu.be/dQw4w9WgXcQ", format="mp4", quality="720p")
print(f"Saved to {path}")
```

It handles submission, polling, retries, and file download for you, with proper exceptions for rate limits, auth errors, and failed jobs. It also supports progress callbacks and step-by-step control (`submit`, `wait`, `fetch`) for more advanced use cases.

Full documentation: [yt-download-client on PyPI](https://pypi.org/project/yt-download-client/) — [source](https://github.com/HkrUchiwa2011/yt-download-client)

### Shell (included)

A ready-to-use shell client is included. It handles submission, polling, and download in one command.

```bash
chmod +x yt-download.sh
# Edit API_BASE and API_KEY at the top of the file
./yt-download.sh https://youtu.be/dQw4w9WgXcQ
./yt-download.sh https://youtu.be/dQw4w9WgXcQ mp3 audio_only
./yt-download.sh https://youtu.be/dQw4w9WgXcQ mp4 720p
```

Requires `curl` and `jq`.

### Python (manual, raw HTTP)

```python
import time
import httpx

BASE = "https://your-api.onrender.com"
HEADERS = {"X-API-Key": "YOUR_KEY"}

def download(url: str, fmt: str = "mp4", quality: str = "best", output: str = "video.mp4"):
    # Submit
    r = httpx.post(f"{BASE}/download", headers=HEADERS, json={
        "url": url, "format": fmt, "quality": quality
    })
    job_id = r.json()["job_id"]
    print(f"Job: {job_id}")

    # Poll
    while True:
        status = httpx.get(f"{BASE}/status/{job_id}", headers=HEADERS).json()
        print(f"Status: {status['status']}")
        if status["status"] == "success":
            break
        if status["status"] == "failure":
            raise RuntimeError(status["error"])
        time.sleep(5)

    # Download
    with httpx.stream("GET", f"{BASE}/file/{job_id}", headers=HEADERS) as r:
        with open(output, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"Saved to {output}")

download("https://youtu.be/dQw4w9WgXcQ", fmt="mp4", quality="720p")
```

### JavaScript / Node.js

```js
const BASE = "https://your-api.onrender.com";
const HEADERS = { "X-API-Key": "YOUR_KEY", "Content-Type": "application/json" };

async function download(url, format = "mp4", quality = "best") {
  const { job_id } = await fetch(`${BASE}/download`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ url, format, quality }),
  }).then(r => r.json());

  console.log("Job:", job_id);

  while (true) {
    const status = await fetch(`${BASE}/status/${job_id}`, { headers: HEADERS }).then(r => r.json());
    console.log("Status:", status.status);
    if (status.status === "success") break;
    if (status.status === "failure") throw new Error(status.error);
    await new Promise(r => setTimeout(r, 5000));
  }

  const res = await fetch(`${BASE}/file/${job_id}`, { headers: HEADERS });
  const buffer = await res.arrayBuffer();
  require("fs").writeFileSync("video.mp4", Buffer.from(buffer));
  console.log("Saved to video.mp4");
}

download("https://youtu.be/dQw4w9WgXcQ", "mp4", "720p");
```

---

## Configuration

All settings are controlled via environment variables. See `.env.example` for the full list.

> The values in `.env.example` are defaults for local development. Set real values when deploying.

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | `changeme` | Auth key — use a strong random value in production |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `MAX_DURATION_SECONDS` | `3600` | Max video duration (seconds) |
| `MAX_FILESIZE_MB` | `500` | Max output file size (MB) |
| `FILE_TTL_MINUTES` | `30` | How long files are kept before cleanup |
| `RATE_LIMIT_PER_MINUTE_IP` | `10` | Max requests per minute per IP |
| `RATE_LIMIT_PER_MINUTE_KEY` | `30` | Max requests per minute per API key |
| `MAX_CONCURRENT_DOWNLOADS` | `5` | Max parallel downloads |
| `PROXY_URL` | _(empty)_ | Optional residential proxy (SOCKS5h) |

---

## If YouTube blocks downloads

Datacenter IPs (Render, AWS, GCP, etc.) are sometimes blocked by YouTube. If you see errors like `Sign in to confirm you're not a bot`, set a residential proxy:

```
PROXY_URL=socks5h://user:pass@gate.provider.com:7000
```

This doesn't happen on all IPs — try without a proxy first.

---

## Legal

Download only content you have the right to download. This tool is intended for personal use. Downloading copyrighted material without permission may violate YouTube's Terms of Service and applicable law. The authors of this project are not responsible for how you use it.

---

## Contributing

PRs are welcome. Open an issue first for anything significant.

## License

MIT
