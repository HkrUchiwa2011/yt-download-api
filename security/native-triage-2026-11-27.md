# Native advisory triage — 2026-11-27

This review applies to the supplied Linux image. Debian sid status and the
version compiled from upstream source are tracked separately. The Debian
tracker snapshot SHA-256 is `4f9cae25829dee5366e35b94a3d429e84583bd3ce75a27acaab4e07215d0a820`.

CVE-2026-125183 and CVE-2026-125185 involve HEVC paths enabled in the build.
Their published affected range ends at 9.0.2. The other new FFmpeg advisories
that still include 9.1 concern disabled ZeroMQ filters or applications that
reuse decoder contexts across users. Each API FFmpeg invocation is a separate
process, including invocations started by yt-dlp.

Expat 2.11.0 upstream lists fixes for CVE-2026-124317, CVE-2026-128241 and
CVE-2026-134703. The Expat [pending issues list](https://github.com/libexpat/libexpat/issues/1160)
still contains undisclosed reports. The post-release fix for CVE-2026-137951
requires an XML_UNICODE build with XML_GE disabled. The supplied build uses
Expat's default narrow-character configuration.

The container scan tracks [CVE-2026-107494](https://security-tracker.debian.org/tracker/CVE-2026-107494)
and [CVE-2026-124709](https://security-tracker.debian.org/tracker/CVE-2026-124709)
in Debian OpenSSL. No trixie package fix was available in the reviewed snapshot.
Both issues require the OpenSSL QUIC stack. The supplied API uses Uvicorn h11
over TCP, and its HTTP clients do not use OpenSSL QUIC. A reverse proxy that
terminates HTTP/3 needs its own OpenSSL assessment.

| Package | Advisory | Assessment |
|---|---|---|
| ffmpeg | CVE-2026-125064 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125065 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125066 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125067 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125095 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125096 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125097 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125098 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125099 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125176 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125177 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125178 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125179 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125180 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125181 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125182 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125183 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125184 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125185 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125186 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125187 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125188 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125189 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125190 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125191 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125192 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125193 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125194 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125195 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125196 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125197 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125198 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125199 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125200 | FFmpeg 9.1 is outside the published affected range (through 9.0.2) |
| ffmpeg | CVE-2026-125201 | Vulkan AV1 acceleration is disabled; advisory excludes FFmpeg 9.0.2 and newer |
| ffmpeg | CVE-2026-133519 | DVD video demuxer is disabled; the advisory also excludes FFmpeg 9.1 |
| ffmpeg | CVE-2026-135703 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135704 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135705 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135706 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135707 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135708 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135709 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135710 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135711 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135712 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135713 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135714 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135715 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135716 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135717 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135718 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135719 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135720 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135721 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135722 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135723 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135724 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135725 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135726 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135727 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135728 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135729 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135730 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135731 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135732 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135733 | The build excludes both zmq and azmq filters and disables networking |
| ffmpeg | CVE-2026-135734 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135735 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135736 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135737 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135738 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135739 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135740 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135741 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135742 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135743 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135744 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-135745 | FFmpeg 9.1 is outside the published affected range (before 9.1) |
| ffmpeg | CVE-2026-137076 | The API uses a fresh FFmpeg process per invocation and never reuses decoder contexts between jobs |
| expat | CVE-2026-134703 | Expat 2.11.0 includes the UTF-16 conversion fix; the runtime also uses the default non-XML_UNICODE build |
| python3.13 | CVE-2026-107784 | Windows-specific tarfile extraction issue; supplied runtime is Linux and request handling does not extract tar archives |
