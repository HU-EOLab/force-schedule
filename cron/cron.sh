#!donotrun

# Do not execute this file!

# Schedule processes with Cron
crontab -e

# Replace all occurences of "force-schedule" below with the full file path of this repository!
FORCE_SCHEDULE=/data/Dagobah/dc/force-schedule
LOG_DIR=$"FORCE_SCHEDULE"/log

# Daily updates each evening
0 20 * * * $"FORCE_SCHEDULE"/bash/cronjobs-daily.sh  $"LOG_DIR"/cronjobs-daily-"$(date +"%Y%m%d%H%M%S")".log 2>&1

# Weekly updates (processing)
# 01:00 AM each monday morning
0 1 * * 1 $"FORCE_SCHEDULE"/bash/cronjobs-weekly.sh $"LOG_DIR"/cronjobs-weekly-"$(date +"%Y%m%d%H%M%S")".log 2>&1
