#!/bin/bash
# runs all scripts for daily datacube maintenance
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e

# parse DIR_TEMP directories from PARAM files
PARAM_FILES=(
  "FILE_ARD_LANDSAT_OLI_PARAM"
  "FILE_ARD_LANDSAT_TM_PARAM"
  "FILE_ARD_SENTINEL2_PARAM")
for NAME in "${PARAM_FILES[@]}";
do
  PARAM_FILE=$("$BIN"/read-config.sh "$NAME")
  FORCE_TEMP_DIR=$(sed -nr 's/^DIR_TEMP.*= *(.+)$/\1/p' "$PARAM_FILE")
  echo "Create DIR_TEMP for $NAME: $FORCE_TEMP_DIR"
  mkdir -p "$FORCE_TEMP_DIR"
  chown "$(id -u)":datacube "$FORCE_TEMP_DIR"
done

# Preprocess Sentinel-2 L1C and Landsat to ARD
# Generate processing report
# Delete downloaded L1 data after preprocessing

echo "Process Sentinel-2"
"$BIN"/process-sentinel2.sh

echo "Process Landsat"
"$BIN"/process-landsat.sh