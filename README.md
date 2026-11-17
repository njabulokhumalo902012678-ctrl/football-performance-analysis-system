# Football Data and Performance Analysis Company - Management System

*Data | Analysis | Opportunities*

One integrated, web-based platform for the whole company: match data collection (phone), validation, analysis,
professional PDF reports, video/scouting, clients and a client portal, finance, marketing, tasks, security and backups.
Six employee positions each get their own dashboard and permissions. Includes coordinate-based shot maps, heat maps and passing networks (only from data actually collected) and a phone-side offline queue for event entry.

> **Technology note (please read).** The specification *recommends* PHP/Laravel + MySQL. This build uses
> **Python 3 + Flask + SQLite** because it could be run and fully tested end-to-end in the build environment
> (PHP and MySQL were not available there, so PHP code could not have been verified). The database schema is plain SQL
> with a **MySQL/MariaDB version provided** (`mysql/schema_mysql.sql`, generated but *not executed against a MySQL server*).
> See `docs/DEPLOYMENT.md` for the MySQL migration path and `docs/KNOWN_LIMITATIONS.md` for what this means.

## Quick start (Windows)

1. Install **Python 3.11 or newer** from python.org (tick *Add Python to PATH*).
2. Double-click **`setup.bat`** (creates a virtual environment, installs libraries, builds a demo database with *fictional* data).
3. Double-click **`run.bat`** and open <http://127.0.0.1:5000> in a browser. On a phone on the same Wi-Fi use `http://<laptop-ip>:5000` after setting `FDPA_HOST=0.0.0.0` (see docs/SETUP_WINDOWS_XAMPP.md).

Demo logins (password for all: `Demo#2026pass`): `md`, `ops`, `analyst`, `scout`, `tech`, `finance`, `collector`, and client portal accounts `client.rudimentary`, `client.city`.
**Delete the demo database before entering real data** (`python manage.py init-db` builds an empty one with only a Technology Lead account).

macOS / Linux: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python manage.py demo && python manage.py run`

## What is in this folder

| Path | Contents |
|---|---|
| `app/` | Application source: `views/` (screens), `metrics.py` (analysis engine), `pdfgen.py` (reports), `workflow.py` (validation), `schema.sql` (database) |
| `manage.py`, `run.py` | Commands: `init-db`, `demo`, `run`, `backup`, `restore`, `test-restore`, `selftest` |
| `mysql/schema_mysql.sql` | MySQL/MariaDB version of the schema (see note above) |
| `tests/` | Automated tests mapped to the 17 acceptance criteria |
| `docs/` | All deliverable documents (list below) |
| `sample_data/` | Sample report PDFs, CSV templates |
| `tools/` | Doc/diagram and MySQL-schema generators |

## Documents (`docs/`)

`IMPLEMENTATION_PLAN.md` (plan, screen designs, phase status) · `DATABASE_DIAGRAM.md` + `database_diagram.png` · `ROLES_PERMISSIONS_MATRIX.md` ·
`EVENT_DATA_DICTIONARY.md` · `METRICS.md` · `USER_GUIDE.md` (all six positions + clients) · `ADMIN_GUIDE.md` · `BACKUP_AND_RESTORE.md` ·
`SETUP_WINDOWS_XAMPP.md` · `DEPLOYMENT.md` · `THIRD_PARTY_AND_COSTS.md` · `ACCEPTANCE_TESTS.md` · `KNOWN_LIMITATIONS.md`

## Core principles built into the system

* **No false statistics.** Every figure is a count of recorded events or a documented formula. If an event category was not collected for a match it shows **Not collected** - never 0. Zero/unknown denominators show **N/A**.
* **Only validated data** goes into final reports. Provisional data is allowed only by explicit choice and the report is stamped PROVISIONAL.
* **Facts vs opinion** are kept apart (analyst notes, scouting records and reports label opinion). Ratings need a rubric-based justification.
* **Everything important is audited**: corrections (with reason), status changes, approvals, sharing, exports, logins, permission changes.
