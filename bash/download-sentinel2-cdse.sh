#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# get config file
if [ $# -ge 1 ]; then
CONFIG=$1
shift
else
  CONFIG="../config/config.txt"
fi

EXTRA_ARGS=("$@")

# parse config file
IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG" )
DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG" )
DIR_CSD_META=$("$BIN"/read-config2.sh "DIR_CSD_META" "$CONFIG" )
DIR_ARD_LOG=$("$BIN"/read-config2.sh "DIR_ARD_LOG" "$CONFIG" )
DIR_SENTINEL2_IMAGES=$("$BIN"/read-config2.sh "DIR_SENTINEL2_IMAGES" "$CONFIG" )
FILE_SENTINEL2_QUEUE=$("$BIN"/read-config2.sh "FILE_SENTINEL2_QUEUE" "$CONFIG" )
FILE_SENTINEL2_AOI=$("$BIN"/read-config2.sh "FILE_SENTINEL2_AOI" "$CONFIG" )
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG"  "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get_uid_gid.sh "$USER_GROUP")

DATERANGE="20260101,20260105"

FN_AOI=$(basename "$FILE_SENTINEL2_AOI")
set -e

if true; then
echo "search with vudongpham/cdse-s2"
docker run --rm \
    -v $FILE_SENTINEL2_AOI:/input/aoi.txt \
    -v $DIR_CSD_META:/input/meta \
    -v $DIR_ARD_LOG:/input/forcelogs \
    vudongpham/cdse-s2 cdse-search \
    --daterange $DATERANGE \
    --cloudcover 0,70 \
    --forcelogs "/input/forcelogs" \
    "/input/aoi.txt" \
    "/input/meta"

  # find latest search result files
  cd $DIR_CSD_META
  cp "$(ls -t query_20*.json | head -n 1)" query_latest.json

fi

# download query_latest.json
if true; then
echo "download S2 files"
  docker run --rm \
    -v $DIR_CSD_META:/input/meta \
    -v $DIR_CREDENTIALS/.cdse:/app/credentials/.cdse \
    -v $DIR_SENTINEL2_IMAGES:/output/images \
    vudongpham/cdse-s2 cdse-download \
    /input/meta/query_latest.json \
    /output/images \
    /app/credentials/.cdse
fi

if true; then
  #echo "unzip downloaded files"

  ls $DIR_SENTINEL2_IMAGES/S2*.zip | parallel -j4 unzip -o -q -d $DIR_SENTINEL2_IMAGES {} || true

  echo "remove zip files if SAVE exists"
  for path in $DIR_SENTINEL2_IMAGES/S2*.zip; do
    basename="${path%.zip}"
    if [ -d "$basename.SAFE" ]; then
      echo "remove $path"
      rm -f "$path"
    fi
  done

  echo "write $FILE_SENTINEL2_QUEUE"
  echo "Add images to queue:"
  ls -d $DIR_SENTINEL2_IMAGES/S2*.SAFE | tee "$FILE_SENTINEL2_QUEUE"
  sed -i 's/$/ QUEUED/' "$FILE_SENTINEL2_QUEUE"
  echo "download & extraction done"
fi
exit 0

