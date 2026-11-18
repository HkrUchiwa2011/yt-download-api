# Native advisory triage — 2026-11-18

Reviewed the 87 newly tracked FFmpeg IDs against the pinned 9.0.2 source,
restricted build flags and upstream fixes. The tracker snapshot SHA-256 is
`41b9801396552598649cf0e3ea243e5c6c480f8f979e954dea1173610bb67cf7`.
Source: https://security-tracker.debian.org/tracker/data/json.

“Omitted” describes our supplied image, not an upstream fix or every deployment.
Per-advisory descriptions and hashes for open findings are in
[native-reviewed.json](native-reviewed.json); patch provenance is in
[../build/README.md](../build/README.md).

| Advisory | Treatment / affected component |
|---|---|
| CVE-2026-125068 | Omitted: Bink video decoder |
| CVE-2026-125069 | Omitted: Motion Pixels decoder |
| CVE-2026-125070 | Omitted: EA TQI decoder |
| CVE-2026-125071 | Omitted: JV decoder |
| CVE-2026-125072 | Omitted: mp3adu decoder (ordinary MP3 decoders do not expose this oversized-packet path) |
| CVE-2026-125073 | Omitted: IMC/IAC decoders |
| CVE-2026-125100 | Omitted: OpenEXR decoder |
| CVE-2026-125101 | Omitted: VMnc decoder |
| CVE-2026-125102 | Omitted: TAK decoder |
| CVE-2026-125103 | Omitted: MPEG-4 ALS decoder / MLZ decompression |
| CVE-2026-125104 | Omitted: APE decoder |
| CVE-2026-125170 | Omitted: Targa decoder |
| CVE-2026-125171 | Omitted: Musepack SV7 decoder |
| CVE-2026-125172 | Omitted: libxevd EVC decoder |
| CVE-2026-125173 | Omitted: libxevd EVC decoder |
| CVE-2026-125174 | Omitted: Hap decoder (also fixed in 9.0.2) |
| CVE-2026-125175 | Omitted: Flash Screen Video decoder |
| CVE-2026-125202 | Omitted: VAAPI HEVC hardware acceleration |
| CVE-2026-125203 | Omitted: Cook decoder (also fixed in 9.0.2) |
| CVE-2026-125204 | Omitted: libwebp encoder |
| CVE-2026-125205 | Backported AV1 temporal-unit OBU limits (ffmpeg-av1-obu-limit.patch); raw OBU demuxers are omitted but the enabled BSF also receives container packets |
| CVE-2026-125206 | Omitted: ProRes KS encoder |
| CVE-2026-125207 | Omitted: Interplay ACM decoder |
| CVE-2026-125208 | Omitted: V4L2 M2M encoding |
| CVE-2026-125209 | Omitted: DVD subtitle encoder (also fixed in 9.0.2) |
| CVE-2026-125210 | Omitted: libaribcaption subtitle decoder |
| CVE-2026-125211 | Omitted: libaribcaption subtitle decoder |
| CVE-2026-125212 | Omitted: VideoToolbox encoders |
| CVE-2026-125213 | Omitted: PSD decoder |
| CVE-2026-125214 | Omitted: Blu-ray LPCM decoder (enabled WAV PCM decoders are separate) |
| CVE-2026-125215 | Omitted: dovi_rpu bitstream filter / Dolby Vision RPU generation |
| CVE-2026-125216 | Omitted: DPX encoder |
| CVE-2026-125217 | Omitted: RoQ DPCM encoder |
| CVE-2026-125218 | Omitted: APNG encoder |
| CVE-2026-125219 | Omitted: VDPAU HEVC hardware acceleration |
| CVE-2026-125220 | Omitted: Mimic decoder |
| CVE-2026-125221 | Removed FLAC decoder, parser and demuxer; not required for YouTube streams |
| CVE-2026-125222 | Omitted: Hap decoder |
| CVE-2026-125223 | Backported VP9 CBS-fragment cleanup on every affected decoder error path (ffmpeg-vp9-cleanup.patch) |
| CVE-2026-125224 | Backported one-time Vorbis extradata parsing (ffmpeg-vorbis-once.patch) |
| CVE-2026-125225 | Backported checked AAC PCE bit-reader initialization (ffmpeg-aac-bitreader.patch) |
| CVE-2026-125226 | Omitted: SBaGen demuxer / wavesynth decoder |
| CVE-2026-125227 | Omitted: JPEG CBS and JPEG-processing bitstream filters |
| CVE-2026-125228 | Omitted: native Vorbis encoder (also fixed in 9.0.2; Vorbis decoding remains enabled) |
| CVE-2026-125229 | Omitted: Huffyuv / FFVHUFF encoders |
| CVE-2026-125230 | Omitted: pcm_rechunk bitstream filter and MXF/GXF/DAUD muxers |
| CVE-2026-125231 | Omitted: ADX decoder |
| CVE-2026-125232 | Omitted: MPEG-1/2/4 video encoders and B-frame motion estimation |
| CVE-2026-125233 | Omitted: DVB subtitle encoder |
| CVE-2026-125234 | Omitted: WavPack encoder |
| CVE-2026-125235 | Omitted: Intel QSV encoders |
| CVE-2026-125236 | Omitted: VVC decoder |
| CVE-2026-125237 | Omitted: DPX decoder and Vulkan acceleration |
| CVE-2026-125238 | Omitted: libxevd EVC decoder |
| CVE-2026-125239 | Omitted: DXVA2/D3D11VA/D3D12VA HEVC acceleration |
| CVE-2026-125240 | Omitted: libsvtjpegxs decoder |
| CVE-2026-125241 | Omitted: FLIC decoder |
| CVE-2026-125242 | Omitted: VDPAU hardware acceleration |
| CVE-2026-125243 | Omitted: JPEG-LS decoder |
| CVE-2026-125244 | Omitted: VVC decoder (also fixed in 9.0.2) |
| CVE-2026-125245 | Omitted: MJPEG decoder / VAAPI and NVDEC acceleration |
| CVE-2026-125246 | Omitted: JPEG CBS and JPEG-processing bitstream filters |
| CVE-2026-125247 | Omitted: TIFF/DNG decoder |
| CVE-2026-125248 | Omitted: Vulkan FFV1 encoder |
| CVE-2026-125249 | Omitted: Vulkan decoding |
| CVE-2026-125250 | Omitted: GIF encoder |
| CVE-2026-125251 | Omitted: VVC decoder |
| CVE-2026-125252 | Omitted: VAAPI decoding |
| CVE-2026-125253 | Backported subtraction-based VP9 superframe bounds (ffmpeg-vp9-size.patch); applies defensively to 32-bit builds, local execution is amd64 |
| CVE-2026-125254 | Omitted: VVC decoder |
| CVE-2026-125255 | Omitted: MJPEG decoder / NVDEC acceleration |
| CVE-2026-125256 | Omitted: Huffyuv encoder and RISC-V RVV encoding routines |
| CVE-2026-125257 | Omitted: Nellymoser encoder |
| CVE-2026-125258 | Omitted: dovi_rpu bitstream filter and libx265/libaom/libsvtav1 encoders |
| CVE-2026-125259 | Omitted: ProRes KS encoder |
| CVE-2026-125260 | Omitted: OpenEXR encoder |
| CVE-2026-125261 | Omitted: SGI encoder |
| CVE-2026-125262 | Omitted: LCEVC decoder |
| CVE-2026-125263 | Omitted: liblcevc_dec integration |
| CVE-2026-125264 | Omitted: JPEG XL parser |
| CVE-2026-125265 | Omitted: NVDEC decoding |
| CVE-2026-125266 | Omitted: SANM decoder |
| CVE-2026-125267 | Omitted: APAC decoder (also fixed in 9.0.2) |
| CVE-2026-125268 | Omitted: CineForm HD decoder |
| CVE-2026-125269 | Omitted: h264_metadata bitstream filter and SEI insertion (stream-copy filters do not invoke that operation) |
| CVE-2026-125270 | Omitted: V4L2 M2M encoders |
| CVE-2026-28731 | Omitted: Interplay MVE decoder / VLC (FFmpeg tracker marks this resolved since 5.0.1) |

Python 3.13 additions:

| Advisory | Treatment |
|---|---|
| CVE-2026-103995 | Backported strict HTTP framing grammar plus optional Content-Length whitespace compatibility (python-http-framing-*.patch) |
| CVE-2026-115559 | IMAP STARTTLS is not used by API routes, workers or configured yt-dlp extractors |
| CVE-2026-16052 | No response-cookie creation or user-controlled Morsel attribute values; cookies are consumed by yt-dlp, not emitted from API input |
