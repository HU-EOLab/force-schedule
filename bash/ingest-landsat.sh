#!/bin/bash
# requires:
# ~/.usgs.txt with USGS machine access credentials
#


# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make sure script exits if any process exits unsuccessfully
set -e


# download landsat data
"$BIN"/download-landsat-links.sh && \
#
# extract the data, build queue
"$BIN"/extract-landsat-links.sh

exit 0
