#!/bin/bash

PROG=$(basename "$0")
BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# tag given?
if [ $# -ne 1 ] ; then
  printf "%s\n" "$PROG expects one variable name as argument. Arguments received: " "$@" 1>&2;
  exit 1
fi
TAG=$1

if [ "$TAG" == "EMAIL_RECIPIENTS" ]; then
  CONFIG=$BIN/../config/email_recipients.txt
else
  CONFIG=$BIN/../config/config.txt
fi

# config found?
if [ ! -r "$CONFIG" ]; then
  echo "$CONFIG not found by $PROG" 1>&2;
  exit 1
fi

# search for tag in config and read value
VALUE=$(grep "^$TAG " "$CONFIG" | sed 's/.* *= *//')

# read successful?
if [ -z "$VALUE" ]; then
  echo "$TAG not found in config.txt" 1>&2;
  exit 1
fi

# print value
echo "$VALUE"

exit 0
