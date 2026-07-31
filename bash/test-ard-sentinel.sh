#!/bin/bash

# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

CONFIG="../config/config.txt"

echo "CONFIG=$CONFIG"


# parse config file
IMAGE=$("$BIN"/read-config2.sh "FORCE_IMAGE" "$CONFIG")
# IMAGE="davidfrantz/force:3.8.01-debug"
# IMAGE="davidfrantz/force:3.8.00"
# IMAGE="davidfrantz/force:3.8.01"
# IMAGE="davidfrantz/force:3.9.02"
# IMAGE="davidfrantz/force:3.10.04-debug"
# IMAGE="davidfrantz/force:3.10.04"
DIR_CREDENTIALS=$("$BIN"/read-config2.sh "DIR_CREDENTIALS" "$CONFIG")
FILE_ARD_SENTINEL2_PARAM=$("$BIN"/read-config2.sh "FILE_ARD_SENTINEL2_PARAM" "$CONFIG")

FILE_DEM=$("$BIN"/read-config2.sh "FILE_DEM" "$FILE_ARD_SENTINEL2_PARAM")
echo "FILE_DEM=$FILE_DEM"
# TEMPLATE="/data/Aldhani/dc/force-schedule/tmp/s2fix/.template_queue.txt"
# cp "$TEMPLATE" "/data/Aldhani/dc/force-schedule/tmp/s2fix/test-queue.txt"
# FILE_ARD_SENTINEL2_PARAM="/data/Aldhani/dc/deu/param/ard/test-germany-operational-sentinel2.prm"
DIR_TEMP=$(sed -nr 's/^DIR_TEMP.*= *(.+)$/\1/p' "$FILE_ARD_SENTINEL2_PARAM")
USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
USER_GROUP=$("$BIN"/get-uid-gid.sh "$USER_GROUP")

echo "PARAM_FILE: $FILE_ARD_SENTINEL2_PARAM"
echo "IMAGE: $IMAGE"
echo "DIR_TEMP: $DIR_TEMP"

# preprocess the S2 L1C to L2 ARD
docker run \
--rm \
-t \
--ulimit nofile=65536:65536 \
-e FORCE_CREDENTIALS=/app/credentials \
-e BOTO_CONFIG=/app/credentials/.boto \
-v "$DIR_CREDENTIALS:/app/credentials" \
-v /data:/data \
-v /mnt:/mnt \
-v "$HOME:$HOME" \
-w "$PWD" \
-u "$USER_GROUP" \
"$IMAGE" \
force-l2ps \
/data/Aldhani/dc/input/sentinel2/images/S2A_MSIL1C_20251226T103501_N0511_R108_T32UNF_20251226T104534.SAFE \
"$FILE_ARD_SENTINEL2_PARAM"

#force-l2ps \
#/data/Aldhani/dc/input/sentinel2/images/S2A_MSIL1C_20251203T102421_N0511_R065_T32TNT_20251203T133542.SAFE \
#"$FILE_ARD_SENTINEL2_PARAM"

#ls -lisa /data/Ferrix/force-temp & \
#mkdir /data/Ferrix/force-temp/mytest

# ls -lisa /data/Ferrix/force-temp
# gdalinfo /data/Aldhani/dc/misc/dem/europe_copernicus.vrt
# gdalinfo --version
# 
# ls -lisa /data/Aldhani/dc/misc/dem/europe_copernicus.vrt
# 



exit 0
