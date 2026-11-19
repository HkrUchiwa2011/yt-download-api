#!/bin/sh
set -eu

# CPython bundles Expat. Rebuild only its matching extension against the fixed
# shared library; _elementtree uses the same parser through pyexpat's C API.
test "$(python -c 'import platform; print(platform.python_version())')" = "$PYTHON_VERSION"
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
    "https://github.com/libexpat/libexpat/releases/download/R_$(printf '%s' "$EXPAT_VERSION" | tr . _)/expat-${EXPAT_VERSION}.tar.xz" \
    -o /tmp/expat.tar.xz
printf '%s  /tmp/expat.tar.xz\n' "$EXPAT_SHA256" | sha256sum -c -
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
    "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
    -o /tmp/python.tar.xz
printf '%s  /tmp/python.tar.xz\n' "$PYTHON_SHA256" | sha256sum -c -
mkdir /tmp/expat /tmp/python /native
tar -xf /tmp/expat.tar.xz -C /tmp/expat --strip-components=1
tar -xf /tmp/python.tar.xz -C /tmp/python --strip-components=1
for fix in /python-patches/*.patch; do
    patch -p1 --fuzz=0 --batch -d /tmp/python < "$fix"
done
mkdir -p /native-stdlib/http
cp /tmp/python/Lib/http/cookiejar.py /tmp/python/Lib/http/client.py /native-stdlib/http/
cd /tmp/expat
./configure --prefix=/opt/expat --disable-static --without-examples --without-tests --without-xmlwf --without-docbook
make -j2
make install
mkdir -p /opt/expat/share/licenses
cp COPYING /opt/expat/share/licenses/
printf 'Expat %s\nSource: https://github.com/libexpat/libexpat/releases\nSHA256: %s\nCPython extension source: https://www.python.org/ftp/python/%s/Python-%s.tar.xz\nSHA256: %s\n' \
    "$EXPAT_VERSION" "$EXPAT_SHA256" "$PYTHON_VERSION" "$PYTHON_VERSION" "$PYTHON_SHA256" > /opt/expat/share/SOURCE.txt
cp /tmp/python/LICENSE /opt/expat/share/licenses/CPython-LICENSE
cp -r /python-patches /opt/expat/share/python-patches
cc -shared -fPIC $(python3-config --cflags) -DPy_BUILD_CORE_MODULE \
    -I/tmp/python/Include/internal -I/tmp/python/Modules -I/tmp/expat -I/opt/expat/include \
    /tmp/python/Modules/pyexpat.c -L/opt/expat/lib -lexpat -Wl,-rpath,/opt/expat/lib \
    -o "/native/pyexpat$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')" \
    $(python3-config --ldflags)
PYTHONPATH=/native python -c "import pyexpat; assert pyexpat.EXPAT_VERSION == 'expat_${EXPAT_VERSION}'"
rm -rf /tmp/python /tmp/expat /tmp/python.tar.xz /tmp/expat.tar.xz
