#!/bin/bash

PROG=$(basename "$0")
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "$PROG: $(date +"%Y-%m-%d %H:%M:%S")"
echo "-----------------------------------------------------------"

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

IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG")
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get_uid_gid.sh "$USER_GROUP")
DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG" "$HOME")

# echo "IMAGE: $IMAGE"
# echo "USER_GROUP: $USER_GROUP"
# echo "DIR_CREDENTIALS: $DIR_CREDENTIALS"
# echo "EXTRA_ARGS: $EXTRA_ARGS"

docker run \
--rm \
-it \
-v "$DIR_CREDENTIALS:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
"${EXTRA_ARGS[@]}"