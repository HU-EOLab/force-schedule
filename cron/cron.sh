#!donotrun

# Do not execute this file!

# Schedule processes with Cron
crontab -e

# Replace all occurences of "force-schedule" below with the full file path of this repository!

# Daily updates each evening
0 20 * * * force-schedule/bash/cronjobs-daily.sh

# Weekly updates (processing)
# 01:00 AM each monday morning
0 1 * * 1 force-schedule/bash/cronjobs-weekly.sh
