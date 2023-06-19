#!/bin/bash

# ============================================================================
# Name: send-matrix-report.sh
# Author: Stefan Ernst
#         Earth Observation Lab, Humboldt-University Berlin
# Desc: Check FORCE processing logs for all scenes processed to ARD
#       the day this script is run and send an report to a matrix room.
#       Also checks for orphaned files from WVP download.
# ============================================================================

set -e

function count_pattern() {
  local pattern="$1"
  local input="$2"
  echo $(grep -c "$pattern" <<< $input)
}

function count_pattern_in_files() {
  local pattern="$1"
  local files="$2"
  echo $(cat $files | grep -c "$pattern")
}

PROG=$(basename "$0")


# Parse command line arguments
ARGS=`getopt -o -m -l matrix -n $0 -- "$@"`
if [ $? != 0 ]; then show_help "$(printf "%s\n       " "Error in command line options. Please check your options.")"; fi
eval set -- "$ARGS"

while :; do
  case "$1" in
    -m|--matrix) matrix=1; shift ;;
    --) shift; break ;;
    *) break
  esac
  shift
done

if [ $# -ne 1 ] || ! ( [[ "$1" =~ ^2[0-9]{3}-[0-1][0-9]-[0-3][0-9]$ ]] && date -d "$1" >/dev/null 2>&1 ); then
  echo "$PROG expects a date in the format YYYY-MM-DD as only argument" 1>&2;
  exit 1
fi

current_date="$1"

bin="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dir_log=$("$bin"/read-config.sh "DIR_ARD_LOG")
dir_wvp=$(dirname $("$bin"/read-config.sh "DIR_WVP"))
email_recipients=$("$bin"/read-config.sh "EMAIL_RECIPIENTS")

# Check FORCE logs
processed_today_paths=$(find "$dir_log" -type f -newermt "$current_date")
processed_today=$(echo "$processed_today_paths" | xargs -L1 -I{} basename "{}")
if [ -z "$processed_today_paths" ]; then
  echo "No log files found for today - please check!" | mail -s "FORCE processing report $current_date" "$email_recipients"
  exit 0
fi

n_processed=$(wc -l <<< $processed_today)
failed_w_error=$(grep ".fail$" <<< $processed_today)
n_failed_w_error=$([ -z "$failed_w_error" ] && echo 0 || echo $(wc -l <<< $failed))
if [[ -z "$failed_w_error" ]]; then
  failed_w_error_mail_text=" "
else
  failed_w_error_mail_text=$(printf "%s\n" "Names of scenes that failed with errors:" "$failed_w_error")
fi

n_successful=$(count_pattern_in_files "Success" "$processed_today_paths")
n_cloudy=$(count_pattern_in_files "Skip" "$processed_today_paths")
n_coregfail=$(count_pattern_in_files "coreg failed" "$processed_today_paths")

n_l7=$(count_pattern "LE07" "$processed_today")
n_l8=$(count_pattern "LC08" "$processed_today")
n_l9=$(count_pattern "LC09" "$processed_today")
n_s2a=$(count_pattern "S2A" "$processed_today")
n_s2b=$(count_pattern "S2B" "$processed_today")


# Check for temporary water vapor folders
wvp_temp_folders=$(find $dir_wvp -name "hdf-20[0-9][0-9]-*" -type d)
if [[ -z "$wvp_temp_folders" ]]; then
  wvp_warning=" "
else
  wvp_warning=$(printf "%s\n" "Temporary wator vapor folders found:" "$wvp_temp_folders")
fi


mail_body=$(cat <<EOF
FORCE processing report ${current_date}

Processed:      ${n_processed}
Successful:     ${n_successful}
Too cloudy:     ${n_cloudy}
Coreg failed:   ${n_coregfail}
Failed w error: ${n_failed_w_error}

Landsat 7:    ${n_l7}
Landsat 8:    ${n_l8}
Landsat 9:    ${n_l9}
Sentinel-2 A: ${n_s2a}
Sentinel-2 B: ${n_s2b}

${failed_w_error_mail_text}

${wvp_warning}
EOF
)

# echo "$mail_body" | mail -s "FORCE processing report $current_date" "$email_recipients"

docker run --rm -it -v /home/ernstste/matrix:/data matrixcommander/matrix-commander -k -m "$mail_body"

echo "$(date +"%H:%m:%S"): Email report sent to $email_recipients"
