#!/bin/sh
# This exact script replaces only Dockerfile RUN packaging to enforce CPU/RAM.
# Inputs are read-only bind mounts; the single owned container is offline.
set -eu
cd /provision/inputs
sha256sum -c INPUTS.sha256
while IFS= read -r package_file; do
  case "$package_file" in *[!A-Za-z0-9_.+-]*|""|.*) exit 21 ;; esac
  dpkg --install "os/$package_file"
done < os/INSTALL_ORDER.txt
test -z "$(dpkg --audit)"
test "$(pkg-config --modversion icu-i18n)" = 70.1
test "$(pkg-config --modversion nlopt)" = 2.7.1
test "$(pkg-config --modversion libxml-2.0)" = 2.9.13
test ! -e /opt/nider/library
mkdir -p /opt/nider/library /opt/nider/provisioning-receipts
Rscript --vanilla /provision/install_locked.R \
  /provision/PACKAGE_PLAN.tsv \
  /provision/inputs/r/SOURCE_ARCHIVES.tsv \
  /provision/inputs/r/archives \
  /opt/nider/library \
  /opt/nider/provisioning-receipts
dpkg-query -W > /opt/nider/provisioning-receipts/system-packages.tsv
printf '%s\n' 'NIDER_OFFLINE_INSTALL_COMPLETE'
