# Administrator guide (Technology Lead)

## Accounts and roles
*Administration → Users*: add employee (initial password; they must change it at first sign-in), edit roles (tick several if needed), **Reset password** (temporary password shown once), **Deactivate/Activate**. You cannot deactivate yourself or remove your own Technology Lead role. Five failed sign-ins lock an account for 15 minutes (reactivating clears it). *Roles and permissions* shows the live matrix. Changing what a role may do means editing `app/constants.py` (`ROLES`): new databases pick it up automatically; for an existing database add/remove rows in the `role_permissions` table to match. Always test and record the change in version control.

## Settings
*Administration → Settings*. Technical keys (session timeout, time-zone offset from UTC - default +2 for Eswatini) need the Technology Lead; company keys need the Managing Director. Every change is audited.

## Audit log
Logins, failed logins, access denials, status changes, event corrections (with reason), approvals, sharing, withdrawals, exports, permission and setting changes, backups. Filter by user, record type, action.

## Errors
Unexpected errors show the user a friendly page, roll back the action, and store the technical trace in *Error log*. Check it daily; the dashboard counts errors in the last 7 days.

## Imports and exports
* Players CSV import (`sample_data/players_import_sample.csv`): all-or-nothing validation; imported profiles are *unverified*.
* Match events CSV: collectors use the fallback on the collection page.
* Exports: each list has *Export CSV* (permission `export.csv`; logged). Dates of birth are never exported. Cells starting with `= + - @` are neutralised against spreadsheet formula injection.

## Video storage
Uploaded video goes to `instance/videos` (outside the web root, streamed only to permitted users, never stored in the database). For large libraries store videos on a company drive and register the link.

## Data sources and permissions
*Football records → Data sources*: record the licence/permission for every external data or video source. Publicly viewable data or footage is **not** automatically free to republish commercially.

## Security checklist
HTTPS in production · `FDPA_HTTPS=1` · strong unique `FDPA_SECRET_KEY` (otherwise `instance/secret_key` is generated) · server firewall · regular backups off the server · least-privilege roles · review audit log · keep Python libraries updated (`pip list --outdated`). Built in: password hashing (PBKDF2-SHA256, 600k rounds), CSRF tokens on every form/POST, parameterised SQL everywhere, auto-escaped templates (XSS), strict Content-Security-Policy (no inline scripts), secure cookies, lockout, inactivity timeout, role checks on every route (server-side).
