#!/bin/bash
# runs all scripts for daily datacube maintenance
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "Run update-force"
"$BIN"/update-force.sh

echo "Run update-landsatlinks"
"$BIN"/update-landsatlinks.sh

# Update Google Cloud Storage metadata, and
# download all Sentinel-2 images that were not already processed to ARD
echo "Run ingest-sentinel2"
"$BIN"/ingest-sentinel2.sh

# generate Landsat links for images that were not already processed to ARD
# download images that were not already downloaded
# extract the images
echo "Run ingest-landsat"
"$BIN"/ingest-landsat.sh

# update MODIS water vapor database
echo "Run update-wvdb.sh"
"$BIN"/update-wvdb.sh

echo "daily updated finished"
