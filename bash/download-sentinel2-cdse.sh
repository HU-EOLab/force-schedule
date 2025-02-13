#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
DIR_CREDENTIALS=$("$BIN"/read-config.sh "DIR_CREDENTIALS")
DIR_CSD_META=$("$BIN"/read-config.sh "DIR_CSD_META")
DIR_ARD_LOG=$("$BIN"/read-config.sh "DIR_ARD_LOG")
DIR_SENTINEL2_IMAGES=$("$BIN"/read-config.sh "DIR_SENTINEL2_IMAGES")
FILE_SENTINEL2_QUEUE=$("$BIN"/read-config.sh "FILE_SENTINEL2_QUEUE")
FILE_SENTINEL2_AOI=$("$BIN"/read-config.sh "FILE_SENTINEL2_AOI")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

# test settings
#DIR_TEST=/data/Aldhani/dc/input/test
# FILE_SENTINEL2_AOI="$DIR_TEST/test_mgrs_tiles.txt"
# DIR_CSD_META="$DIR_TEST/meta"
#DIR_SENTINEL2_IMAGES="$DIR_TEST/images"
#FILE_SENTINEL2_QUEUE="$DIR_TEST/queue.txt"

FN_AOI=$(basename "$FILE_SENTINEL2_AOI")

# download Sentinel-2 L1C images that weren't processed to ARD yet
# -u "$USER_GROUP" \

if false; then
echo "search with vudongpham/cdse-s2"
docker run --rm \
    -v $FILE_SENTINEL2_AOI:/input/aoi.txt \
    -v $DIR_CSD_META:/input/meta \
    -v $DIR_ARD_LOG:/input/forcelogs \
    vudongpham/cdse-s2 search \
    --daterange 20240101,20991231 \
    --cloudcover 0,70 \
    --forcelogs "/input/forcelogs" \
    "/input/aoi.txt" \
    "/input/meta"

  # find latest search result files
  cd $DIR_CSD_META
  cp "$(ls -t query_20*.json | head -n 1)" query_latest.json

fi

# download query_latest.json
if false; then
echo "download S2 files"
  docker run --rm \
    -v $DIR_CSD_META:/input/meta \
    -v $DIR_CREDENTIALS/.cdse:/app/credentials/.cdse \
    -v $DIR_SENTINEL2_IMAGES:/output/images \
    vudongpham/cdse-s2 download \
    /input/meta/query_latest.json \
    /output/images \
    /app/credentials/.cdse
fi

if true; then
  #echo "unzip downloaded files"
  #ls $DIR_SENTINEL2_IMAGES/S2*.zip | parallel -j4 unzip -o -dq $DIR_SENTINEL2_IMAGES {}

  echo "remove zip files if SAVE exists"
  for path in $DIR_SENTINEL2_IMAGES/S2*.zip; do
    basename="${path%.zip}"
    if [ -d "$basename.SAFE" ]; then
      echo "remove $path"
      rm -f "$path"
    fi
  done

  echo "write $FILE_SENTINEL2_QUEUE"
  echo "ls $DIR_SENTINEL2_IMAGES"
  ls -d $DIR_SENTINEL2_IMAGES/S2*.SAFE > "$FILE_SENTINEL2_QUEUE"
  sed -i 's/$/ QUEUED/' "$FILE_SENTINEL2_QUEUE"
fi
exit 0

