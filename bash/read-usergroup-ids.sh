#!/bin/bash
# reads the user name and user group from the config.txt
# and returns the related IDs
# fr example: "userX:groupY" will be returned as 1234:4321, with 1234 being the user ID etc.
# PROG=`basename $0`;
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
USER_GROUP=$("$BIN"/read-config.sh "USER_GROUP")

# IFS=', ' read -r -a array <<< "$string"
UNAME=$(grep -Po '^.*(?=:)' <<< $USER_GROUP)
GNAME=$(grep -Po '[^:]+$' <<< $USER_GROUP)

echo "$(id -u "$UNAME"):$(getent group "$GNAME" | awk -F: '{print $3}')"
exit 0
# getent group datacube | awk -F: '{print $3}'
