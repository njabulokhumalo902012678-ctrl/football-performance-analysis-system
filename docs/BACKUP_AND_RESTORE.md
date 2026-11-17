# Backup and restoration

## What is backed up
`fdpa_backup_YYYYMMDD_HHMMSS.zip` = a **consistent snapshot of the database** (SQLite online-backup API, safe while the system is running) + all generated report PDFs. Uploaded video files are **not** included - back up `instance/videos` separately.

## Create
* In the app: *Administration → Backups → Create backup now* (stored in `backups/`, downloadable).
* Command line / scheduled: `python manage.py backup`.
* **Automation (Windows Task Scheduler)**: Action `C:\fdpa\.venv\Scripts\python.exe`, arguments `manage.py backup`, start in `C:\fdpa`, trigger daily 02:00. Linux cron: `0 2 * * * cd /opt/fdpa && .venv/bin/python manage.py backup`.
* **Copy backups off the machine** (second disk, company cloud drive, encrypted USB) - a backup on the same laptop is not safe. Keep 7 daily + 4 weekly + 12 monthly copies.

## Test (do this monthly - an untested backup is not a backup)
*Backups → Test restore of latest backup* or `python manage.py test-restore`. It unpacks the newest backup into a scratch folder, runs `PRAGMA integrity_check` and compares record counts with the live data. Results are logged and shown on the Technology dashboard. Differences in counts are expected if work happened after the backup.

## Restore for real (disaster recovery)
1. Stop the web application.
2. `python manage.py restore backups\fdpa_backup_YYYYMMDD_HHMMSS.zip` and type `YES`. The current database is kept as `fdpa.sqlite3.before_restore`; report PDFs are restored to `instance/reports`.
3. Start the application; sign in; check the dashboard counts and open a recent report.
4. Record the incident and the data-loss window (time between backup and failure) in the task list.

## Retention and deletion
Retention rule is stored in Settings (default 5 years). Deleting a person's data on request: remove/anonymise the player record (`players`) and related reports; old backups still contain it until they expire - document this in client agreements.
