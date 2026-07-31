#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

CONFIG="../config/config.txt"

# parse config file
IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG")

DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG")
FILE_ARD_SENTINEL2_PARAM=$("$BIN"/read-config2.sh "FILE_ARD_SENTINEL2_PARAM" "$CONFIG")
DIR_TEMP=$(sed -nr 's/^DIR_TEMP.*= *(.+)$/\1/p' "$FILE_ARD_SENTINEL2_PARAM")
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get-uid-gid.sh "$USER_GROUP")

# preprocess the S2 L1C to L2 ARD
echo "PARAM_FILE: $FILE_ARD_SENTINEL2_PARAM"
echo "IMAGE: $IMAGE"
echo "DIR_TEMP: $DIR_TEMP"

docker run \
--rm \
--ulimit nofile=65536:65536 \
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
