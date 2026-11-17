"""Administration: users and roles, settings, audit log, backups and restore test, error log, imports, permission matrix."""
import csv
import io
import secrets
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from .. import constants as C
from ..db import ex, get_setting, q, scalar, set_setting
from ..security import audit, diff, hash_password, has_perm, password_problems, perm_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client":
        abort(403)


# ============================================================================= users
@bp.route("/users")
@perm_required("users.manage")
def users():
    rows = q("SELECT u.*, (SELECT GROUP_CONCAT(r.name, ', ') FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=u.id) AS roles "
             "FROM users u WHERE u.user_type='employee' ORDER BY u.is_active DESC, u.full_name")
    return render_template("admin/users.html", rows=rows)


def _user_form(u=None):
    roles = q("SELECT * FROM roles WHERE code!='client' ORDER BY is_primary DESC, id")
    cur = {r["role_id"] for r in q("SELECT role_id FROM user_roles WHERE user_id=?", (u["id"],))} if u else set()
    if request.method == "POST":
        name, email = request.form.get("full_name", "").strip(), request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip().lower()
        chosen = {int(x) for x in request.form.getlist("roles") if x.isdigit()}
        chosen = {r["id"] for r in roles if r["id"] in chosen}
        errs = []
        if not name or not username or "@" not in email:
            errs.append("Name, username and a valid email are required.")
        if not chosen:
            errs.append("Assign at least one role.")
        dup = scalar("SELECT COUNT(*) FROM users WHERE (lower(username)=? OR lower(email)=?) AND id != ?", (username, email, u["id"] if u else 0))
        if dup:
            errs.append("Another account already uses that username or email.")
        pw = request.form.get("password", "")
        if not u:
            probs = password_problems(pw)
            if probs:
                errs.append("Initial password needs: " + ", ".join(probs) + ".")
        if u and u["id"] == g.user["id"] and "technology_lead" in g.role_codes:
            if "technology_lead" not in {r["code"] for r in roles if r["id"] in chosen}:
                errs.append("You cannot remove your own Technology Lead role.")
        if errs:
            for e in errs:
                flash(e, "error")
            return render_template("admin/user_form.html", u=u, roles=roles, cur=chosen, form=request.form), 422
        if u:
            ex("UPDATE users SET full_name=?, email=?, username=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (name, email, username, u["id"]))
            ex("DELETE FROM user_roles WHERE user_id=?", (u["id"],))
            uid = u["id"]
            audit("user.update", "users", uid, {"roles": sorted(chosen)})
        else:
            uid = ex("INSERT INTO users (username, email, full_name, password_hash, must_change_password) VALUES (?,?,?,?,1)", (username, email, name, hash_password(pw)))
            audit("user.create", "users", uid, {"roles": sorted(chosen)})
        for rid in chosen:
            ex("INSERT INTO user_roles (user_id, role_id) VALUES (?,?)", (uid, rid))
        flash("User saved." + ("" if u else " They must change the password at first sign-in."), "ok")
        return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", u=u, roles=roles, cur=cur, form=None)


@bp.route("/users/new", methods=["GET", "POST"])
@perm_required("users.manage")
def user_new():
    return _user_form(None)


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@perm_required("users.manage")
def user_edit(uid):
    u = q("SELECT * FROM users WHERE id=? AND user_type='employee'", (uid,), one=True)
    if not u:
        abort(404)
    return _user_form(u)


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@perm_required("users.manage")
def user_toggle(uid):
    u = q("SELECT * FROM users WHERE id=? AND user_type='employee'", (uid,), one=True)
    if not u:
        abort(404)
    if u["id"] == g.user["id"]:
        flash("You cannot deactivate your own account.", "error")
    else:
        ex("UPDATE users SET is_active=?, failed_logins=0, locked_until=NULL WHERE id=?", (0 if u["is_active"] else 1, uid))
        audit("user.deactivate" if u["is_active"] else "user.activate", "users", uid)
        flash("Account " + ("deactivated." if u["is_active"] else "activated."), "ok")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/reset", methods=["POST"])
@perm_required("users.manage")
def user_reset(uid):
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not u:
        abort(404)
    temp = secrets.token_urlsafe(9) + "A1"
    ex("UPDATE users SET password_hash=?, must_change_password=1, failed_logins=0, locked_until=NULL WHERE id=?", (hash_password(temp), uid))
    audit("user.password_reset", "users", uid)
    flash(f"Temporary password for {u['username']} (shown once): {temp}", "ok")
    return redirect(url_for("admin.users"))


@bp.route("/roles")
@perm_required("users.manage", "audit.view")
def roles_matrix():
    roles = q("SELECT * FROM roles WHERE code!='client' ORDER BY is_primary DESC, id")
    perms = q("SELECT * FROM permissions ORDER BY code")
    grants = {(r["role_id"], r["permission_id"]) for r in q("SELECT * FROM role_permissions")}
    return render_template("admin/roles.html", roles=roles, perms=perms, grants=grants)


# ============================================================================= settings
STRATEGIC = [("company_name", "Company name", "text"), ("company_tagline", "Tagline", "text"), ("currency", "Currency code", "text"),
             ("invoice_prefix", "Invoice number prefix", "text"), ("default_tax_rate", "Default tax rate (%)", "text"),
             ("confidentiality_statement", "Report confidentiality statement", "textarea"), ("rating_rubric", "Analyst rating rubric", "textarea"),
             ("retention_note", "Retention and deletion rule", "textarea"), ("portal_show_services", "Show agreed services in client portal (1/0)", "text")]
TECHNICAL = [("session_timeout_minutes", "Automatic logout after inactivity (minutes)", "text"), ("timezone_offset_hours", "Local time offset from UTC (hours)", "text")]


@bp.route("/settings", methods=["GET", "POST"])
@perm_required("settings.strategic", "system.admin")
def settings():
    can_s, can_t = has_perm("settings.strategic"), has_perm("system.admin")
    if request.method == "POST":
        changed = {}
        for keys, allowed in ((STRATEGIC, can_s), (TECHNICAL, can_t)):
            if not allowed:
                continue
            for k, _l, _t in keys:
                if k in request.form:
                    v = request.form[k].strip()
                    if k in ("session_timeout_minutes",) and not (v.isdigit() and 5 <= int(v) <= 480):
                        flash("Inactivity timeout must be between 5 and 480 minutes.", "error")
                        continue
                    if k == "timezone_offset_hours":
                        try:
                            if not -12 <= float(v) <= 14:
                                raise ValueError
                        except ValueError:
                            flash("Time offset must be between -12 and 14.", "error")
                            continue
                    if k in ("default_tax_rate",):
                        try:
                            if not 0 <= float(v) <= 100:
                                raise ValueError
                        except ValueError:
                            flash("Tax rate must be between 0 and 100.", "error")
                            continue
                    old = get_setting(k)
                    if old != v:
                        set_setting(k, v)
                        changed[k] = {"from": old, "to": v}
        if changed:
            audit("settings.update", "settings", None, changed)
            flash("Settings saved.", "ok")
        return redirect(url_for("admin.settings"))
    vals = {k: get_setting(k, "") for k, _, _ in STRATEGIC + TECHNICAL}
    return render_template("admin/settings.html", strategic=STRATEGIC, technical=TECHNICAL, vals=vals, can_s=can_s, can_t=can_t)


# ============================================================================= audit
@bp.route("/audit")
@perm_required("audit.view")
def audit_log():
    where, args = ["1=1"], []
    for key, col in (("user", "a.user_id"), ("entity", "a.entity")):
        v = request.args.get(key, "")
        if v:
            where.append(f"{col}=?")
            args.append(v)
    act = request.args.get("action", "").strip()
    if act:
        where.append("a.action LIKE ?")
        args.append(act + "%")
    page = max(request.args.get("page", 1, type=int), 1)
    per = 100
    total = scalar(f"SELECT COUNT(*) FROM audit_logs a WHERE {' AND '.join(where)}", args)
    rows = q("SELECT a.*, u.full_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id "
             f"WHERE {' AND '.join(where)} ORDER BY a.id DESC LIMIT {per} OFFSET {(page - 1) * per}", args)
    users_ = q("SELECT id, full_name FROM users ORDER BY full_name")
    entities = q("SELECT DISTINCT entity FROM audit_logs WHERE entity IS NOT NULL ORDER BY entity")
    return render_template("admin/audit.html", rows=rows, total=total, page=page, per=per, users=users_, entities=entities,
                           f=dict(user=request.args.get("user", ""), entity=request.args.get("entity", ""), action=act))


# ============================================================================= backups
def _backup_dir():
    d = Path(current_app.config["BACKUP_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_backup(user_id=None):
    """Consistent database snapshot (SQLite online backup) plus generated reports, zipped."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = _backup_dir() / f"fdpa_backup_{ts}.zip"
    tmp = Path(tempfile.mkdtemp())
    try:
        snap = tmp / "fdpa.sqlite3"
        src = sqlite3.connect(current_app.config["DATABASE"])
        dst = sqlite3.connect(snap)
        src.backup(dst)
        dst.close()
        src.close()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "fdpa.sqlite3")
            rdir = Path(current_app.config["REPORT_DIR"])
            for f in rdir.glob("*.pdf"):
                z.write(f, f"reports/{f.name}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_restore(zip_path):
    """Restore a backup into a scratch folder and verify it. Never touches the live database."""
    tmp = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extract("fdpa.sqlite3", tmp)
        con = sqlite3.connect(tmp / "fdpa.sqlite3")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        live = sqlite3.connect(current_app.config["DATABASE"])
        diffs = []
        for t in ("users", "clubs", "players", "matches", "match_events", "reports", "invoices", "audit_logs"):
            a = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            b = live.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if a != b:
                diffs.append(f"{t}: backup {a} vs live {b}")
        con.close()
        live.close()
        return integrity == "ok", integrity, diffs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@bp.route("/backups", methods=["GET", "POST"])
@perm_required("system.admin")
def backups():
    if request.method == "POST":
        act = request.form.get("action")
        try:
            if act == "backup":
                out = make_backup(g.user["id"])
                ex("INSERT INTO backup_logs (action, file_path, size_bytes, status, message, user_id) VALUES ('backup',?,?,'ok','Backup created',?)",
                   (out.name, out.stat().st_size, g.user["id"]))
                audit("backup.create", "backup_logs", None, {"file": out.name})
                flash(f"Backup created: {out.name}", "ok")
            elif act == "test":
                files = sorted(_backup_dir().glob("fdpa_backup_*.zip"))
                if not files:
                    flash("Create a backup first.", "error")
                else:
                    ok, integrity, diffs = test_restore(files[-1])
                    note = "Restore test passed" if ok and not diffs else ("Restore test: " + (integrity if not ok else "; ".join(diffs)))
                    ex("INSERT INTO backup_logs (action, file_path, size_bytes, status, message, user_id) VALUES ('restore_test',?,?,?,?,?)",
                       (files[-1].name, files[-1].stat().st_size, "ok" if ok else "failed", note[:250], g.user["id"]))
                    audit("backup.restore_test", "backup_logs", None, {"file": files[-1].name, "ok": ok, "diffs": diffs})
                    flash(note + (" (differences are expected if data changed after the backup)" if ok and diffs else ""), "ok" if ok else "error")
        except Exception as e:           # report, but let the global handler log details
            current_app.logger.exception("backup failed")
            ex("INSERT INTO backup_logs (action, status, message, user_id) VALUES (?, 'failed', ?, ?)", (act or "backup", str(e)[:250], g.user["id"]))
            flash("The backup operation failed - see the error log.", "error")
        return redirect(url_for("admin.backups"))
    logs = q("SELECT b.*, u.full_name FROM backup_logs b LEFT JOIN users u ON u.id=b.user_id ORDER BY b.id DESC LIMIT 50")
    files = sorted(_backup_dir().glob("fdpa_backup_*.zip"), reverse=True)
    return render_template("admin/backups.html", logs=logs, files=[(f.name, f.stat().st_size) for f in files])


@bp.route("/backups/<name>")
@perm_required("system.admin")
def backup_download(name):
    if "/" in name or "\\" in name or not name.startswith("fdpa_backup_") or not name.endswith(".zip"):
        abort(404)
    p = _backup_dir() / name
    if not p.exists():
        abort(404)
    audit("backup.download", "backup_logs", None, {"file": name})
    return send_file(p, as_attachment=True)


# ============================================================================= errors / imports
@bp.route("/errors")
@perm_required("system.admin")
def errors():
    rows = q("SELECT e.*, u.full_name FROM error_logs e LEFT JOIN users u ON u.id=e.user_id ORDER BY e.id DESC LIMIT 100")
    return render_template("admin/errors.html", rows=rows)


@bp.route("/imports", methods=["GET", "POST"])
@perm_required("import.data", "system.admin")
def imports():
    if request.method == "POST":
        if not has_perm("import.data"):
            abort(403)
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Choose a .csv file.", "error")
            return redirect(url_for("admin.imports"))
        try:
            text = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            flash("File must be UTF-8 CSV.", "error")
            return redirect(url_for("admin.imports"))
        reader = csv.DictReader(io.StringIO(text))
        if "full_name" not in (reader.fieldnames or []):
            flash("The file needs a 'full_name' column. Columns: full_name, position, team, shirt_number, nationality.", "error")
            return redirect(url_for("admin.imports"))
        ok, bad = [], []
        teams = {r["name"].lower(): r["id"] for r in q("SELECT id, name FROM teams")}
        for i, r in enumerate(reader, start=2):
            r = {k: (v or "").strip() for k, v in r.items() if k}
            if not r.get("full_name"):
                bad.append(f"Row {i}: full_name is empty.")
                continue
            if r.get("position") and r["position"] not in C.POSITIONS:
                bad.append(f"Row {i}: position '{r['position']}' is not one of the approved positions.")
                continue
            tid = None
            if r.get("team"):
                tid = teams.get(r["team"].lower())
                if tid is None:
                    bad.append(f"Row {i}: team '{r['team']}' does not exist - create it first.")
                    continue
            shirt = None
            if r.get("shirt_number"):
                if not r["shirt_number"].isdigit():
                    bad.append(f"Row {i}: shirt_number must be a whole number.")
                    continue
                shirt = int(r["shirt_number"])
            ok.append((r["full_name"][:190], r.get("position") or None, tid, shirt, r.get("nationality") or None))
        job = ex("INSERT INTO import_jobs (job_type, filename, status, rows_total, rows_ok, rows_failed, errors, user_id) VALUES ('players_csv',?,?,?,?,?,?,?)",
                 (f.filename[:200], "failed" if bad else "complete", len(ok) + len(bad), 0 if bad else len(ok), len(bad), "\n".join(bad)[:4000] or None, g.user["id"]))
        if bad:
            for b in bad[:10]:
                flash(b, "error")
            flash("Nothing imported - fix the rows above and upload again.", "error")
        else:
            for (n, pos, tid, shirt, nat) in ok:
                pid = ex("INSERT INTO players (full_name, position, current_team_id, shirt_number, nationality, verification_status, profile_source) VALUES (?,?,?,?,?, 'unverified', 'CSV import')", (n, pos, tid, shirt, nat))
                if tid:
                    ex("INSERT INTO player_team_history (player_id, team_id, start_date, shirt_number) VALUES (?,?,date('now'),?)", (pid, tid, shirt))
            audit("import.players", "import_jobs", job, {"rows": len(ok)})
            flash(f"{len(ok)} players imported as unverified profiles.", "ok")
        return redirect(url_for("admin.imports"))
    jobs = q("SELECT j.*, u.full_name FROM import_jobs j LEFT JOIN users u ON u.id=j.user_id ORDER BY j.id DESC LIMIT 50")
    return render_template("admin/imports.html", jobs=jobs, can_import=has_perm("import.data"))
