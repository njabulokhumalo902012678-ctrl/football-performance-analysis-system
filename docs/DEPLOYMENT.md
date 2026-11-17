# Deployment

## 1. Small company, one machine (recommended start)
* Run on a laptop/mini-PC or a small cloud VM (1 vCPU, 1-2 GB RAM is plenty for a small company).
* Use a production WSGI server instead of the development server: `pip install waitress` then `waitress-serve --listen=127.0.0.1:8000 --call app:create_app`.
* Put a web server with **HTTPS** in front: Caddy (automatic certificates, simplest), Nginx + Let's Encrypt, or **XAMPP Apache** with `mod_proxy` (`ProxyPass / http://127.0.0.1:8000/`) and a certificate.
* Environment variables: `FDPA_HTTPS=1`, `FDPA_SECRET_KEY=<64 random hex chars>`, optionally `FDPA_DB`, `FDPA_SMTP_HOST/PORT/USER/PASSWORD/FROM` (password-reset emails; otherwise reset links are written to `instance/outbox`).
* Run as a service: Windows - NSSM or Task Scheduler "at startup"; Linux - systemd unit.
* Schedule daily backups and monthly restore tests (`BACKUP_AND_RESTORE.md`).
* Mobile data collection from stadiums needs the server reachable from the internet over HTTPS.

## 2. Production checklist
- [ ] Demo database deleted; `init-db` used; strong passwords; demo accounts do not exist.
- [ ] HTTPS working; `FDPA_HTTPS=1`; HTTP redirects to HTTPS.
- [ ] Firewall: only 80/443 open. Server OS updates enabled.
- [ ] Backups automated, copied off-site, restore tested.
- [ ] Error log reviewed; time-zone offset correct.
- [ ] Privacy: only data you are authorised to hold; permissions recorded in *Data sources*.

## 3. Moving to MySQL / MariaDB (XAMPP) - optional, when needed
The spec recommends MySQL. The schema is provided (`mysql/schema_mysql.sql`) but was **generated, not executed on a MySQL server** by the original author. Steps and effort:
1. Create a utf8mb4 database and a **limited** MySQL user; load `schema_mysql.sql`; test.
2. Replace the data layer `app/db.py` with a MySQL driver (`PyMySQL`/`mysql-connector`), use `%s` placeholders instead of `?`.
3. Port the few SQLite-specific statements: `INSERT ... ON CONFLICT(...) DO UPDATE` → `ON DUPLICATE KEY UPDATE`; `date('now')`/`datetime('now', ...)` → `CURDATE()`/`NOW() - INTERVAL`; `GROUP_CONCAT(x, ', ')` → `GROUP_CONCAT(x SEPARATOR ', ')`; `INSERT OR IGNORE` → `INSERT IGNORE`; `PRAGMA table_info` → `information_schema`; the backup code → `mysqldump`.
4. Run `tests/` against a MySQL test database; migrate data via CSV export/import in dependency order.
Budget roughly 2-4 developer days plus testing. The Python analytics must connect with a **read-only** MySQL user restricted to the tables it needs (never root).

## 4. Scaling later
Move SQLite → MySQL/PostgreSQL, store videos/reports in object storage, add a task queue for large PDF batches, add SSO if the company grows.
