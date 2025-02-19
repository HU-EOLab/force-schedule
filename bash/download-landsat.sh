#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
DIR_CREDENTIALS=$("$BIN"/read-config.sh "DIR_CREDENTIALS")
DIR_ARD_LOG=$("$BIN"/read-config.sh "DIR_ARD_LOG")
DIR_LANDSAT_IMAGES=$("$BIN"/read-config.sh "DIR_LANDSAT_IMAGES")
FILE_LANDSAT_AOI=$("$BIN"/read-config.sh "FILE_LANDSAT_AOI")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

# query USGS M2M API for Landsat product bundles and download what hasn't been processed to ARD yet
docker run \
  --rm \
  -v "$DIR_CREDENTIALS:/app/credentials" \
  -v /data:/data \
  -v /mnt:/mnt \
  -v "$HOME:$HOME" \
  -w "$PWD" \
  -u $(id -u):$(id -g) \
  "$IMAGE" \
  force-level1-landsat search \
    "$FILE_LANDSAT_AOI" \
    "$DIR_LANDSAT_IMAGES" \
    --sensor TM,OLI \
    --cloudcover 0,70 \
    --level L1TP \
    --tier T1 \
    --forcelogs "$DIR_ARD_LOG" \
    --secret "/app/credentials/.usgs.txt" \
    --download

exit 0
