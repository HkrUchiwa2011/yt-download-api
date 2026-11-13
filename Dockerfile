FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS media-build

ARG FFMPEG_VERSION=9.0.2
ARG FFMPEG_SHA256=8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl xz-utils nasm patch libmp3lame-dev zlib1g-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY build/build-ffmpeg.sh /build-ffmpeg.sh
COPY build/patches /patches
COPY build/test-native.c /test-native.c
RUN sh /build-ffmpeg.sh

FROM media-build AS xml-build
ARG EXPAT_VERSION=2.10.0
ARG EXPAT_SHA256=c624ba2998fc65df1163a49641ff3f9ab73138b11641d92c86bee0fb01b1bc7f
ARG PYTHON_VERSION=3.13.18
ARG PYTHON_SHA256=abb0102e6d4ae027509bcb82327d9dd85515b44a3ba8ad538cfc5e9847029f68
COPY build/build-pyexpat.sh /build-pyexpat.sh
RUN sh /build-pyexpat.sh

FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS dependencies

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR=/tmp/runtime DENO_DIR=/tmp/runtime/deno
ARG ZLIB_VERSION=1:1.3.dfsg+really1.3.1-1+deb13u1
ARG LAME_VERSION=3.100-6+b3
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmp3lame0=${LAME_VERSION} zlib1g=${ZLIB_VERSION} ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=media-build /opt/ffmpeg /opt/ffmpeg
COPY --from=xml-build /opt/expat /opt/expat
COPY --from=xml-build /native/ /usr/local/lib/python3.13/lib-dynload/
ENV PATH=/opt/ffmpeg/bin:$PATH
RUN python -c "import pyexpat, xml.etree.ElementTree as E; assert pyexpat.EXPAT_VERSION == 'expat_2.10.0'; assert E.fromstring('<check/>').tag == 'check'"
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
RUN groupadd --gid 10001 downloader && useradd --uid 10001 --gid 10001 --no-create-home downloader \
    && mkdir -p /tmp/yt-downloads /tmp/runtime && chown 10001:10001 /tmp/yt-downloads /tmp/runtime
COPY --chown=10001:10001 app ./app

FROM dependencies AS tests
# The full Debian binary only generates fixtures; processing uses /opt/ffmpeg.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt
COPY --chown=10001:10001 tests ./tests
COPY --from=media-build /native-tests /opt/native-tests
ENV FIXTURE_FFMPEG=/usr/bin/ffmpeg
ENV NATIVE_TEST_BINARY=/opt/native-tests/test-native
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM dependencies AS runtime
# Dependency installers and their vendored libraries are unnecessary at runtime.
RUN python -m pip uninstall -y pip
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["python", "-m", "app.server"]
