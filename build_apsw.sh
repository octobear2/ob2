#!/bin/bash

set -e

VERSION=3.9.2-r1
SQLITE_VERSION=3.9.2

wget -O apsw.zip \
    "https://github.com/rogerbinns/apsw/releases/download/${VERSION}/apsw-${VERSION}.zip"

rm -rf "apsw-${VERSION}"
unzip apsw.zip
cd "apsw-${VERSION}"
python setup.py fetch --version="${SQLITE_VERSION}" --missing-checksum-ok --all build --enable-all-extensions install
