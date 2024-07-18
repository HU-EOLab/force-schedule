#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
DIR_ARD_LOG=$("$BIN"/read-config.sh "DIR_ARD_LOG")
DIR_CREDENTIALS=$("$BIN"/read-config.sh "DIR_CREDENTIALS")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

# call FORCE image with R to run the R script that renames failed log files from *.log to *.fail
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
    "$BIN"/../rstats/rename-failed-logs.r  \
    "$DIR_ARD_LOG"

exit 0
