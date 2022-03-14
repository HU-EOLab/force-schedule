#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
DIR_ARD_LOG=$("$BIN"/read-config.sh "DIR_ARD_LOG")
DIR_ARD_REPORT=$("$BIN"/read-config.sh "DIR_ARD_REPORT")
USER_GROUP=$("$BIN"/read-config.sh "USER_GROUP")

# current time
TIME=$(date +"%Y%m%d%H%M%S")

# preprocess the S2 L1C to L2 ARD
docker run \
--rm \
-e FORCE_CREDENTIALS=/app/credentials \
-e BOTO_CONFIG=/app/credentials/.boto \
-v "$HOME:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
force-level2-report \
  -o "$DIR_ARD_REPORT/report_$TIME.html" \
  "$DIR_ARD_LOG"

exit 0
