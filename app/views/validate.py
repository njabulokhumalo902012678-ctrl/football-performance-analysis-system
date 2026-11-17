"""Validation queue: review submitted data, raise/resolve issues, return for correction, approve for analysis."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import constants as C
from ..db import ex, q, scalar
from ..security import audit, has_perm
from ..workflow import open_error_count, run_validation, set_status
from .matches import match_row

bp = Blueprint("validate", __name__, url_prefix="/validate")


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client" or not has_perm("events.validate", "events.return", "events.view"):
        abort(403)


@bp.route("/")
def queue():
    rows = q("SELECT m.id, m.match_code, m.kickoff, m.status, ht.name AS home, at.name AS away, "
             "(SELECT COUNT(*) FROM match_events e WHERE e.match_id=m.id) AS events, "
             "(SELECT COUNT(*) FROM validation_issues v WHERE v.match_id=m.id AND v.status='open' AND v.severity='error') AS errors, "
             "(SELECT COUNT(*) FROM validation_issues v WHERE v.match_id=m.id AND v.status='open' AND v.severity='warning') AS warnings "
             "FROM matches m JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
             "WHERE m.status IN ('data_submitted','validation_required','corrections_required') ORDER BY m.kickoff")
    return render_template("validate/queue.html", rows=rows)


@bp.route("/<int:mid>")
def review(mid):
    m = match_row(mid)
    events = q("SELECT e.*, t.name AS type_name, t.code, p.full_name AS player, rp.full_name AS related, tm.name AS team, u.full_name AS collector "
               "FROM match_events e JOIN event_types t ON t.id=e.event_type_id LEFT JOIN players p ON p.id=e.player_id "
               "LEFT JOIN players rp ON rp.id=e.related_player_id JOIN teams tm ON tm.id=e.team_id LEFT JOIN users u ON u.id=e.collector_id "
               "WHERE e.match_id=? ORDER BY CASE e.period WHEN '1H' THEN 1 WHEN '2H' THEN 2 ELSE 3 END, COALESCE(e.minute,999), e.id", (mid,))
    issues = q("SELECT v.*, e.id AS eid FROM validation_issues v LEFT JOIN match_events e ON e.id=v.event_id WHERE v.match_id=? "
               "ORDER BY CASE v.status WHEN 'open' THEN 0 ELSE 1 END, CASE v.severity WHEN 'error' THEN 0 ELSE 1 END, v.id", (mid,))
    apps = q("SELECT a.*, p.full_name, tm.name AS team FROM appearances a JOIN players p ON p.id=a.player_id JOIN teams tm ON tm.id=a.team_id "
             "WHERE a.match_id=? ORDER BY a.team_id, a.role, p.full_name", (mid,))
    scope = {r["category"] for r in q("SELECT category FROM match_collection_scope WHERE match_id=? AND collected=1", (mid,))}
    source = q("SELECT * FROM data_sources WHERE id=1", one=True)
    return render_template("validate/review.html", m=m, events=events, issues=issues, apps=apps, scope=scope, source=source,
                           can_validate=has_perm("events.validate"), can_return=has_perm("events.return"),
                           can_correct=has_perm("events.correct"),
                           open_errors=open_error_count(mid),
                           open_warnings=scalar("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND status='open' AND severity='warning'", (mid,)))


@bp.route("/<int:mid>/check", methods=["POST"])
def recheck(mid):
    match_row(mid)
    if not has_perm("events.validate", "events.return"):
        abort(403)
    n = run_validation(mid, g.user["id"])
    audit("validation.check", "matches", mid, {"issues": n})
    flash(f"Checks complete: {n} open issue(s).", "ok" if n == 0 else "info")
    return redirect(url_for("validate.review", mid=mid))


@bp.route("/<int:mid>/issue", methods=["POST"])
def add_issue(mid):
    match_row(mid)
    if not has_perm("events.validate", "events.return"):
        abort(403)
    msg = request.form.get("message", "").strip()[:255]
    sev = request.form.get("severity", "error")
    eid = request.form.get("event_id", type=int)
    if not msg or sev not in ("error", "warning"):
        flash("Describe the issue.", "error")
    else:
        if eid and not scalar("SELECT COUNT(*) FROM match_events WHERE id=? AND match_id=?", (eid, mid)):
            eid = None
        ex("INSERT INTO validation_issues (match_id, event_id, issue_type, severity, message, raised_by) VALUES (?,?,?,?,?,?)",
           (mid, eid, "manual", sev, msg, g.user["id"]))
        audit("validation.issue", "matches", mid, {"message": msg})
        flash("Issue recorded.", "ok")
    return redirect(url_for("validate.review", mid=mid))


@bp.route("/<int:mid>/issue/<int:iid>", methods=["POST"])
def resolve_issue(mid, iid):
    match_row(mid)
    if not has_perm("events.validate"):
        abort(403)
    iss = q("SELECT * FROM validation_issues WHERE id=? AND match_id=?", (iid, mid), one=True)
    if not iss:
        abort(404)
    action = request.form.get("action")
    if action == "ignore" and iss["severity"] == "error":
        flash("Errors cannot be ignored - correct the data or mark the issue resolved once fixed.", "error")
    elif action in ("resolved", "ignored", "ignore"):
        status = "ignored" if action.startswith("ignor") else "resolved"
        ex("UPDATE validation_issues SET status=?, resolved_by=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?", (status, g.user["id"], iid))
        audit("validation.issue_" + status, "validation_issues", iid, {"message": iss["message"]})
        flash("Issue updated. Re-run checks to confirm the data is clean.", "ok")
    return redirect(url_for("validate.review", mid=mid))


@bp.route("/<int:mid>/return", methods=["POST"])
def send_back(mid):
    m = match_row(mid)
    if not has_perm("events.return"):
        abort(403)
    note = request.form.get("note", "").strip()
    if not note:
        flash("Say what needs correcting so the collector knows what to fix.", "error")
        return redirect(url_for("validate.review", mid=mid))
    if m["status"] not in ("validation_required", "data_submitted", "data_validated"):
        flash("This match is not awaiting validation.", "error")
        return redirect(url_for("validate.review", mid=mid))
    if m["status"] == "data_validated" and not has_perm("events.correct"):
        abort(403)
    ex("UPDATE match_events SET validation_status='returned' WHERE match_id=? AND validation_status IN ('submitted','validated')", (mid,))
    set_status(mid, "corrections_required", g.user["id"], note[:200])
    ex("UPDATE collection_assignments SET status='assigned' WHERE match_id=? AND assignment_role IN ('collector','backup_collector')", (mid,))
    for r in q("SELECT user_id FROM collection_assignments WHERE match_id=? AND assignment_role='collector'", (mid,)):
        ex("INSERT INTO tasks (title, description, assigned_to, department, priority, related_type, related_id, created_by) VALUES (?,?,?,?,?,?,?,?)",
           (f"Correct data for {m['match_code']}", note, r["user_id"], "Operations", "high", "match", mid, g.user["id"]))
    audit("validation.returned", "matches", mid, {"note": note})
    flash("Match data returned for correction.", "ok")
    return redirect(url_for("validate.queue"))


@bp.route("/<int:mid>/approve", methods=["POST"])
def approve(mid):
    m = match_row(mid)
    if not has_perm("events.validate"):
        abort(403)
    if m["status"] not in ("validation_required", "data_submitted"):
        flash("This match is not awaiting validation.", "error")
        return redirect(url_for("validate.review", mid=mid))
    run_validation(mid, g.user["id"])
    errors = open_error_count(mid)
    warnings = scalar("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND status='open' AND severity='warning'", (mid,))
    if errors:
        flash(f"Cannot approve: {errors} unresolved error(s). Fix or return the data.", "error")
    elif warnings and not request.form.get("ack_warnings"):
        flash(f"{warnings} warning(s) are still open. Resolve/ignore them, or tick the box to approve with warnings.", "error")
    else:
        if warnings:
            ex("UPDATE validation_issues SET status='ignored', resolved_by=?, resolved_at=CURRENT_TIMESTAMP WHERE match_id=? AND status='open'", (g.user["id"], mid))
        ex("UPDATE match_events SET validation_status='validated' WHERE match_id=? AND validation_status IN ('submitted','draft','returned')", (mid,))
        ex("UPDATE appearances SET verification_status='verified' WHERE match_id=?", (mid,))
        set_status(mid, "data_validated", g.user["id"], "Validated for analysis")
        audit("validation.approved", "matches", mid, {"warnings_acknowledged": warnings})
        flash("Match data validated. It can now be used in analysis and reports.", "ok")
        return redirect(url_for("analysis.match_view", mid=mid))
    return redirect(url_for("validate.review", mid=mid))
