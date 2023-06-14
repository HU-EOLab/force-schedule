#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
DIR_CREDENTIALS=$("$BIN"/read-config.sh "DIR_CREDENTIALS")
DIR_CSD_META=$("$BIN"/read-config.sh "DIR_CSD_META")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

# update CSD metadata
docker run \
--rm \
-e FORCE_CREDENTIALS=/app/credentials \
-e BOTO_CONFIG=/app/credentials/.boto \
-v "$DIR_CREDENTIALS:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
force-level1-csd -u "$DIR_CSD_META" -s s2a

exit 0

