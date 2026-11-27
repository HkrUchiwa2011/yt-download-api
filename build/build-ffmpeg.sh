#!/bin/sh
set -eu

# Source verification and patch provenance are documented in build/README.md.
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
    "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" -o /tmp/ffmpeg.tar.xz
printf '%s  /tmp/ffmpeg.tar.xz\n' "$FFMPEG_SHA256" | sha256sum -c -
mkdir /tmp/ffmpeg
tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg --strip-components=1
cd /tmp/ffmpeg
for fix in /patches/*.patch; do
    patch -p1 --fuzz=0 --batch < "$fix"
done

# yt-dlp handles downloads; FFmpeg only processes local media.
# Enable video stream copying and audio decoding for MP3 conversion.
./configure \
    --prefix=/opt/ffmpeg --extra-version=yt1 --extra-ldflags=-Wl,-rpath,/opt/ffmpeg/lib \
    --disable-autodetect --disable-everything --disable-network \
    --disable-doc --disable-debug --disable-static --enable-shared \
    --disable-avdevice --disable-swscale --disable-hwaccels \
    --enable-ffmpeg --enable-ffprobe --enable-pthreads --enable-zlib \
    --enable-libmp3lame --enable-encoder=libmp3lame \
    --enable-decoder=aac,aac_latm,opus,vorbis,mp3,mp3float,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,h264,hevc,vp8,vp9,av1 \
    --enable-parser=aac,aac_latm,opus,vorbis,mpegaudio,h264,hevc,vp8,vp9,av1 \
    --enable-demuxer=mov,matroska,mp3,aac,wav,ogg,mpegts \
    --enable-muxer=mp3,mp4,ipod,webm,matroska,null \
    --enable-protocol=file,pipe \
    --enable-filter=abuffer,abuffersink,anull,aformat,aresample,atrim,asetpts,buffer,buffersink,null,trim,setpts \
    --enable-bsf=aac_adtstoasc,extract_extradata,h264_mp4toannexb,hevc_mp4toannexb,av1_frame_merge,av1_frame_split,vp9_superframe,vp9_superframe_split
make -j2
make install
mkdir /native-tests
cc -Wall -Wextra -Werror /test-native.c -I/opt/ffmpeg/include -L/opt/ffmpeg/lib \
    -Wl,-rpath,/opt/ffmpeg/lib -lavformat -lavcodec -lavutil -o /native-tests/test-native
for case in encryption hdr aac av1-packet av1-buffer vorbis flac-disabled; do
    /native-tests/test-native "$case"
done
mkdir -p /opt/ffmpeg/share/licenses
cp COPYING.LGPLv2.1 LICENSE.md /opt/ffmpeg/share/licenses/
cp ffbuild/config.log config_components.h /opt/ffmpeg/share/
cp -r /patches /opt/ffmpeg/share/patches
printf 'FFmpeg %s\nSource: https://ffmpeg.org/releases/ffmpeg-%s.tar.xz\nSHA256: %s\n' \
    "$FFMPEG_VERSION" "$FFMPEG_VERSION" "$FFMPEG_SHA256" > /opt/ffmpeg/share/SOURCE.txt
rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz
