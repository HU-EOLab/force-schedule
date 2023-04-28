#!/bin/bash
# PROG=`basename $0`;
# call this to update the baseimage that is used for co-registration of S2 to Landsat
# see https://force-eo.readthedocs.io/en/latest/howto/coreg.html#tut-coreg

BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse config file
IMAGE=$("$BIN"/read-config.sh "FORCE_IMAGE")
FILE_BASE_PARAM=$("$BIN"/read-config.sh "FILE_BASE_PARAM")
USER_GROUP=$("$BIN"/read-usergroup-ids.sh)

echo $FILE_BASE_PARAM
# update CSD metadata
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
force-higher-level "$FILE_BASE_PARAM"

exit 0