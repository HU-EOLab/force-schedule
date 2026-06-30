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
IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG")
DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG")
# FILE_ARD_SENTINEL2_PARAM=$("$BIN"/read-config.sh "FILE_ARD_SENTINEL2_PARAM")

TEMPLATE="/data/Aldhani/dc/force-schedule/tmp/s2fix/.template_queue.txt"
cp "$TEMPLATE" "/data/Aldhani/dc/force-schedule/tmp/s2fix/test-queue.txt"
FILE_ARD_SENTINEL2_PARAM="/data/Aldhani/dc/deu/param/ard/test-germany-operational-sentinel2.prm"
DIR_TEMP=$(sed -nr 's/^DIR_TEMP.*= *(.+)$/\1/p' "$FILE_ARD_SENTINEL2_PARAM")
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get_uid_gid.sh "$USER_GROUP")

echo "Run TEST QUEUE: $FILE_ARD_SENTINEL2_PARAM"
echo "IMAGE: $IMAGE"
echo "DIR_TEMP: $DIR_TEMP"
# preprocess the S2 L1C to L2 ARD
docker run \
--rm \
-t \
-e FORCE_CREDENTIALS=/app/credentials \
-e BOTO_CONFIG=/app/credentials/.boto \
-v "$DIR_CREDENTIALS:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-v "$DIR_TEMP:$DIR_TEMP" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
force-level2 \
  "$FILE_ARD_SENTINEL2_PARAM"

exit 0
