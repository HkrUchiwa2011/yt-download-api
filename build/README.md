# Native components in the supplied Docker image

The Python application can also run outside Docker. These choices apply to the
image shipped by this repository; other deployments manage their own native
packages.

The build uses separate compiler stages. Compilers, fixture-generation FFmpeg
and test binaries are absent from the final runtime. Source downloads require
the SHA-256 digests pinned in `Dockerfile`.

## FFmpeg 9.0.2-yt1

The official 9.0.2 release archive was verified with the release signature and
the signing key published at https://ffmpeg.org/ffmpeg-devel.asc. Fingerprint:
`FCF986EA15E6E293A5644F10B4322F04D67658D8`.

`build-ffmpeg.sh` enables local MP4/WebM/MPEG-TS and audio processing, video
stream copying and MP3 encoding. yt-dlp downloads streams; FFmpeg has only
`file` and `pipe` protocols. XML, DASH/HLS manifest demuxers, SFTP/RTSP,
devices, graphical libraries, hardware accelerators and unused codecs are
omitted. MPEG-TS input permits processing segments downloaded by yt-dlp's
native HLS downloader. This is not a general-purpose FFmpeg installation.

The release also needs the following targeted patches:

| Patch | Reason and provenance |
|---|---|
| `ffmpeg-encryption-free.patch` | CVE-2026-107678: iterative release of encryption-init records. First patch from https://code.ffmpeg.org/FFmpeg/FFmpeg/pulls/24593; the full proposal is not merged into the release. |
| `ffmpeg-pssh-limit.patch` | Local hardening for the same advisory: reject more than 64 PSSH records per MOV input to bound the existing quadratic append path. Avoids introducing the proposal's new unreleased API. |
| `ffmpeg-hdr.patch` | CVE-2026-107676: preserve unconditional saturation fields and avoid unwritten output bytes. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/2c2f6e96e31795ae95a8f8323a493ffbc493111f |

Patches apply with zero fuzz; a changed upstream layout fails the build instead
of silently omitting fixes. `test-native.c` checks a 100,000-node list on a
128 KiB stack and HDR metadata round trips without tone mapping. Media tests
exercise actual conversions, stream merging and rejection of excessive PSSH
metadata.

FFmpeg libraries are shared and include development headers. LGPL license
files, source URL/digest, applied patches and configuration are installed in
`/opt/ffmpeg/share`. Debian's shared libmp3lame is used for MP3 encoding.
Application code remains MIT; these components retain their own licenses.
When distributing binaries, provide corresponding sources and patches as
required by those licenses.

## Expat 2.10.0 and CPython 3.13.18

The Python base image embeds Expat 2.9.0 in `pyexpat`; package-only scans do
not inventory it. Version 2.10.0 fixes CVE-2026-113351, CVE-2026-115506,
CVE-2026-117610 and CVE-2026-118370 (see the upstream release's `Changes`).

`build-pyexpat.sh` rebuilds the matching CPython extension against a shared
Expat 2.10.0 library. `_elementtree` uses that same parser via the C API.
The build verifies the base Python version, source digests, loaded parser
version and an ElementTree parse. Sources and licenses are recorded in
`/opt/expat/share`. Changing the Python base version requires updating the
matching source version/digest and extension destination together.

Source-built components must be reviewed separately from Debian package scan
results. A scanner failing to inventory a binary does not establish that it
has no vulnerabilities. Upstream Expat also tracks undisclosed issues at
https://github.com/libexpat/libexpat/issues/1160; the latest release does not
guarantee absence of unknown or pending flaws. Metadata and jobs run in
bounded child processes; Docker limits remain relevant.

## Local verification

Start an isolated Redis bound to localhost, as described in the main README,
then run:

```bash
docker build --target tests -t yt-download-api:tests .
docker run --rm --network host \
  -e TEST_REDIS_URL=redis://127.0.0.1:16379/15 yt-download-api:tests
docker build -t yt-download-api:local .
```

The test image uses `/usr/bin/ffmpeg` only to create fixtures; transfers,
conversion, merging and probes use production `/opt/ffmpeg/bin` executables.
The `tests` stage is separate from the default final `runtime` stage.
