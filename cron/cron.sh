#!donotrun

# Do not execute this file!

# Schedule processes with Cron
crontab -e

# Replace all occurences of "force-schedule" below with the full file path of this repository!
# Daily updates each evening
0 20 * * * /data/Dagobah/dc/force-schedule/bash/cronjobs-daily.sh > /data/Dagobah/dc/force-schedule/log/cronjobs-daily-"$(date +"%Y%m%d%H%M%S")".log 2>&1

# Weekly updates (processing)
# 01:00 AM each monday morning
0 1 * * 1 /data/Dagobah/dc/force-schedule/bash/cronjobs-weekly.sh > /data/Dagobah/dc/force-schedule/log/cronjobs-weekly-"$(date +"%Y%m%d%H%M%S")".log 2>&1
