#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file

DIR_CREDENTIALS=$("$BIN"/read-config.sh "DIR_CREDENTIALS")
DIR_ARD_LOG=$("$BIN"/read-config.sh "DIR_ARD_LOG")
DIR_LANDSAT_IMAGES=$("$BIN"/read-config.sh "DIR_LANDSAT_IMAGES")

FILE_LANDSAT_AOI=$("$BIN"/read-config.sh "FILE_LANDSAT_AOI")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

# DIR_ARD_LOG=/data/Aldhani/dc/deu/log
# DIR_LANDSAT_IMAGES=/data/Aldhani/dc/input/test/images
# FILE_LANDSAT_AOI=/data/Aldhani/dc/deu/vector/WRS2_allowed-footprints.txt
# query USGS M2M API for Landsat product bundles and download what hasn't been processed to ARD yet

# ls -al "$DIR_LANDSAT_IMAGES"
# cat "$FILE_LANDSAT_AOI"

echo "FILE_LANDSAT_AOI=$FILE_LANDSAT_AOI"
echo "DIR_LANDSAT_IMAGES=$DIR_LANDSAT_IMAGES"
echo "DIR_ARD_LOG=$DIR_ARD_LOG"

docker run --rm \
  -v "$DIR_CREDENTIALS:/app/credentials" \
  -v /data:/data \
  -v /mnt:/mnt \
  -v "$HOME:$HOME" \
  -w "$PWD" \
  -u $(id -u):$(id -g) \
"ernstste/landsatlinks:latest" \
landsatlinks search \
"$FILE_LANDSAT_AOI" \
"$DIR_LANDSAT_IMAGES" \
--sensor TM,OLI \
--secret "/app/credentials/.usgs.txt" \
--cloudcover 0,70 \
--level L1TP \
--tier T1 \
--forcelogs "$DIR_ARD_LOG" \
--download
  
  
exit 0
