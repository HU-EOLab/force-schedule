#!/bin/bash

PROG=$(basename "$0")
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "$PROG: $(date +"%Y-%m-%d %H:%M:%S")"
echo "-----------------------------------------------------------"

# make sure script exits if any process exits unsuccessfully
set -e


CONFIG="../config/config.txt"

IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG")
IMAGE="davidfrantz/force:3.9.02"
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get-uid-gid.sh "$USER_GROUP")
DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG" "$HOME")
EXTRA_ARGS=("$@")

echo "CONFIG: $CONFIG"
echo "IMAGE: $IMAGE"
echo "EXTRA_ARGS: $EXTRA_ARGS"

docker run \
--rm \
-it \
--ulimit nofile=16384:16384 \
-v "$DIR_CREDENTIALS:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-v "$DIR_TEMP:$DIR_TEMP" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
"${EXTRA_ARGS[@]}"