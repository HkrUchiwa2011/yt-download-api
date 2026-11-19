# Native components in the supplied Docker image

The Python application can also run outside Docker. These choices apply to the
image shipped by this repository; other deployments manage their own native
packages.

The build uses separate compiler stages. Compilers, fixture-generation FFmpeg
and test binaries are absent from the final runtime. Source downloads require
the SHA-256 digests pinned in `Dockerfile`.

## FFmpeg 9.0.2-yt2

The official 9.0.2 release archive was verified with the release signature and
the signing key published at https://ffmpeg.org/ffmpeg-devel.asc. Fingerprint:
`FCF986EA15E6E293A5644F10B4322F04D67658D8`.

`build-ffmpeg.sh` enables local MP4/WebM/MPEG-TS and audio processing, video
stream copying and MP3 encoding. yt-dlp downloads streams; FFmpeg has only
`file` and `pipe` protocols. XML, DASH/HLS manifest demuxers, SFTP/RTSP,
devices, graphical libraries, hardware accelerators and unused codecs are
omitted. MPEG-TS input permits processing segments downloaded by yt-dlp's
native HLS downloader. FLAC decoding, parsing and demuxing are excluded: they
are unnecessary for YouTube streams and expose CVE-2026-125221's recursive
parser. This is not a general-purpose FFmpeg installation.

The release also needs the following targeted patches:

| Patch | Reason and provenance |
|---|---|
| `ffmpeg-encryption-free.patch` | CVE-2026-107678: iterative release of encryption-init records. First patch from https://code.ffmpeg.org/FFmpeg/FFmpeg/pulls/24593; the full proposal is not merged into the release. |
| `ffmpeg-pssh-limit.patch` | Local hardening for the same advisory: reject more than 64 PSSH records per MOV input to bound the existing quadratic append path. Avoids introducing the proposal's new unreleased API. |
| `ffmpeg-hdr.patch` | CVE-2026-107676: preserve unconditional saturation fields and avoid unwritten output bytes. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/2c2f6e96e31795ae95a8f8323a493ffbc493111f |
| `ffmpeg-aac-bitreader.patch` | CVE-2026-125225: reject oversized AAC PCE packets before reading bits. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/3b1cbb5e0f66b85d15f1d3527436520b3f4711ec |
| `ffmpeg-av1-obu-limit.patch` | CVE-2026-125205: limit temporal units to 65,536 OBUs, including accumulation across packets. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/c90bbc2036bac67e95777638bdc86157a775858a |
| `ffmpeg-vorbis-once.patch` | CVE-2026-125224: parse invalid Vorbis extradata only once. The release already has the `extradata_parsed` field. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/90f5e61a1da2dcc0050169af8ca593530f26071b |
| `ffmpeg-vp9-cleanup.patch` | CVE-2026-125223: reset the CBS fragment on affected VP9 decoder error paths. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/bcce3232016695f5e482867519c45727a0a2a2c9 |
| `ffmpeg-vp9-size.patch` | CVE-2026-125253: avoid superframe-size addition overflow on 32-bit builds. https://code.ffmpeg.org/FFmpeg/FFmpeg/commit/6280907da48c4dd78f95ef5c713a29c7702153a3 |

Patches apply with zero fuzz; a changed upstream layout fails the build instead
of silently omitting fixes. `test-native.c` checks a 100,000-node list on a
128 KiB stack and HDR metadata round trips without tone mapping. Media tests
exercise actual conversions, stream merging and rejection of excessive PSSH
metadata. The native harness also rejects oversized AAC packets, bounds AV1
OBUs in one packet and across packets, checks cleanup after rejected AV1 input,
counts a single parse of corrupt Vorbis extradata, and confirms FLAC is absent.
Media fixtures cover VP9/Opus and AV1/AAC stream merging and Vorbis-to-MP3
conversion. Local execution is on amd64; the 32-bit VP9 arithmetic fix is
backported and reviewed but has not been executed on a 32-bit target.

FFmpeg libraries are shared and include development headers. LGPL license
files, source URL/digest, applied patches and configuration are installed in
`/opt/ffmpeg/share`, including `config_components.h` for the compiled component
inventory. Debian's shared libmp3lame is used for MP3 encoding.
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

The supplied Python 3.13.18 library also includes a targeted `http.cookiejar`
backport for CVE-2026-124249. It checks cookie policy before an expired cookie
may remove an existing one. The patch comes from CPython's 3.13 proposal
https://github.com/python/cpython/pull/161581 at commit
`76a88d2e4d8c86af4cd2fdde2284a0bc1c3e4f26`; it is not yet in the selected release.
The modified library and patch provenance are shipped in the runtime; domain,
path and blocked-domain regressions run in the Docker test target. Remove the
backport once the selected upstream release includes the fix.

`http.client` also includes CVE-2026-103995's framing fix from CPython commits
[`2eb2af805c156ca52b316bb4ced5e0ab3971d0ae`](https://github.com/python/cpython/commit/2eb2af805c156ca52b316bb4ced5e0ab3971d0ae)
and [`9f52b443c002cccfb54bda0706a9276b6b4a109d`](https://github.com/python/cpython/commit/9f52b443c002cccfb54bda0706a9276b6b4a109d).
They validate chunk sizes and Content-Length before integer conversion, while
preserving valid optional whitespace around Content-Length. Only library diffs
are backported; Docker regressions exercise malformed and valid framing without
network access. Both library patches and CPython's license ship with the runtime.
An installation outside this image must update or patch its own Python runtime;
these backports do not change a host's standard library or the SDK's interpreter.

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
