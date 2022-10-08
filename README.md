# force-schedule
Schedule FORCE processing to periodically download and process Sentinel-2 and Landsat data

Set up:
- 
- Make sure you have the required access credentials for Google Cloud Storage (Sentinel-2) and the USGS M2M API (Landsat) \
  Info: [Google Cloud Storage](https://force-eo.readthedocs.io/en/latest/howto/level1-csd.html#gsutil-configuration), [USGS M2M API](https://github.com/ernstste/landsatlinks#requirements) \
  Make sure that the `.boto` file (S2) and the `.usgs.txt` file (Landsat) are in your home directory
- Edit paths in `config/config_example.txt` and rename the file to `config/config.txt`
- Edit paths in `cron/cron_example.sh` and rename the file to `cron/cron.sh` 

Optional:
- 
- Send email reports about ARD procesing status: \
  Add email recipients in `config/email_recipients_example.txt` and rename the file to `config/email_recipients.txt`, \
  and edit the `cron/cron.sh` script to enable email reports.
