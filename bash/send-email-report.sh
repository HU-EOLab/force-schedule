#!/bin/bash

# ============================================================================
# Name: send-email-report.sh
# Author: Stefan Ernst
#         Earth Observation Lab, Humboldt-University Berlin
# Date: 2022-06-24
# Update: 2022-09-08
# Desc: Check FORCE processing logs for all scenes processed to ARD
#       the day this script is run and send an email report.
#       Also checks for orphaned files from WVP download.
# ============================================================================


function count_by_sensor() {
  echo $(echo "$2" | grep -o "$1" | wc -l)
}

PROG=$(basename "$0")
if [ $# -ne 1 ] || ! ( [[ "$1" =~ ^2[0-9]{3}-[0-1][0-9]-[0-3][0-9]$ ]] && date -d "$1" >/dev/null 2>&1 ); then
  echo "$PROG expects a date in the format YYYY-MM-DD as only argument" 1>&2;
  exit 1
fi

current_date="$1"

bin="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dir_log=$("$bin"/read-config.sh "DIR_ARD_LOG")
dir_wvp=$(dirname $("$bin"/read-config.sh "DIR_WVP"))
email_recipients=$("$bin"/read-config.sh "EMAIL_RECIPIENTS")

processed_today=$(find "$dir_log" -type f -newermt "$current_date" -exec basename {} \;) # | tee $current_date"_scenes_processed.txt")
failed=$(grep ".fail$" <<< $processed_today)
n_processed=$([ -z "$processed_today" ] && echo 0 || echo $(wc -l <<< $processed_today))
n_failed=$([ -z "$failed" ] && echo 0 || echo $(wc -l <<< $failed))
n_successful=$((n_processed-n_failed))

n_l8=$(count_by_sensor "LC08" "$processed_today")
n_l9=$(count_by_sensor "LC09" "$processed_today")
n_s2a=$(count_by_sensor "S2A" "$processed_today")
n_s2b=$(count_by_sensor "S2B" "$processed_today")


# Check for temporary water vapor folders
wvp_temp_folders=$(find $dir_wvp -name "hdf-20[0-9][0-9]-*" -type d)
if [[ -z "$wvp_temp_folders" ]]; then
  wvp_warning=" "
else
  wvp_warning=$(printf "%s\n" "Warning" "Temporary wator vapor folders found:" "$wvp_temp_folders")
fi


mail_body=$(cat <<EOF
FORCE processing report ${current_date}
Processed:    ${n_processed}
Successful:   ${n_successful}
Failed:       ${n_failed}

Landsat 8:    ${n_l8}
Landsat 9:    ${n_l9}
Sentinel-2 A: ${n_s2a}
Sentinel-2 B: ${n_s2b}

Names of failed scenes:
${failed}

${wvp_warning}

EOF
)

echo "$mail_body" | mail -s "FORCE processing report $current_date" "$email_recipients"
