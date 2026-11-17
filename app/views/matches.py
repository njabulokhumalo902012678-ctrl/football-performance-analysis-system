"""Fixtures, assignments, checklists, official result, collection scope, squads and appearances."""
import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import constants as C
from ..db import ex, local_now, q, scalar
from ..forms import F, form_value, parse_form
from ..security import audit, diff, has_perm, login_required, perm_required
from ..workflow import can_collect, is_assigned, set_status
from .dashboard import GROUPS, _args, group_sql

bp = Blueprint("matches", __name__, url_prefix="/matches")

CHECKLIST_DEFAULT = ["Collector confirmed attendance", "Backup collector arranged", "Lineups received from both teams",
                     "Collection device charged and tested", "Transport and access to venue arranged",
                     "Video permission checked (if video analysis needed)", "Client brief confirmed"]
ROLE_FIELDS = [("collector", "Data collector"), ("backup_collector", "Backup collector"),
               ("analyst", "Football analyst"), ("video_analyst", "Video / scouting analyst")]
EMP = ("users", "full_name", "user_type='employee' AND is_active=1")

MATCH_FIELDS = [
    F("competition_id", "Competition", "fk", fk=("competitions", "name")),
    F("season_id", "Season", "fk", fk=("seasons", "name")),
    F("home_team_id", "Home team", "fk", fk=("teams", "name"), req=True),
    F("away_team_id", "Away team", "fk", fk=("teams", "name"), req=True),
    F("kickoff", "Date and kick-off time (local)", "datetime", req=True),
    F("venue_id", "Venue", "fk", fk=("venues", "name")),
    F("duration_minutes", "Scheduled match length (minutes)", "int", default=90, help="Used for playing minutes. Use 120 if extra time is played."),
    F("collection_deadline", "Collection deadline", "datetime"),
    F("client_id", "Commissioning client", "fk", fk=("clients", "name")),
    F("notes", "Notes", "textarea"),
]
ASSIGN_FIELDS = [F(f"as_{k}", label, "fk", fk=EMP) for k, label in ROLE_FIELDS]


def match_row(mid):
    m = q("SELECT m.*, ht.name AS home, at.name AS away, v.name AS venue, c.name AS competition, s.name AS season, cl.name AS client "
          "FROM matches m JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
          "LEFT JOIN venues v ON v.id=m.venue_id LEFT JOIN competitions c ON c.id=m.competition_id "
          "LEFT JOIN seasons s ON s.id=m.season_id LEFT JOIN clients cl ON cl.id=m.client_id WHERE m.id=?", (mid,), one=True)
    if not m:
        abort(404)
    return m


def can_edit_collection(m):
    """Lineups, official result and scope. Ops may not touch data after validation (correction process instead)."""
    if m["status"] not in C.PRE_SUBMISSION:           # submitted/validated data changes only through the correction process
        return has_perm("events.correct")
    return has_perm("squad.edit", "events.correct") or (has_perm("events.collect") and can_collect(g.user["id"], m["id"]))


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client" or not has_perm("match.view"):
        abort(403)


@bp.route("/")
def list_view():
    where, args = ["1=1"], {}
    group = request.args.get("group", "")
    if group in GROUPS:
        where.append(group_sql(group))
        args.update(_args(group, local_now()))
    st = request.args.get("status", "")
    if st:
        where.append("m.status = :st")
        args["st"] = st
    term = request.args.get("q", "").strip()
    if term:
        where.append("(ht.name LIKE :t OR at.name LIKE :t OR m.match_code LIKE :t)")
        args["t"] = f"%{term}%"
    mine = request.args.get("mine")
    if mine:
        where.append("EXISTS (SELECT 1 FROM collection_assignments ca WHERE ca.match_id=m.id AND ca.user_id=:me)")
        args["me"] = g.user["id"]
    rows = q("SELECT m.*, ht.name AS home, at.name AS away, v.name AS venue, "
             "(SELECT u.full_name FROM collection_assignments ca JOIN users u ON u.id=ca.user_id WHERE ca.match_id=m.id AND ca.assignment_role='collector' LIMIT 1) AS collector, "
             "(SELECT COUNT(*) FROM match_events e WHERE e.match_id=m.id) AS n_events "
             "FROM matches m JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id LEFT JOIN venues v ON v.id=m.venue_id "
             f"WHERE {' AND '.join(where)} ORDER BY m.kickoff DESC LIMIT 300", args)
    if request.args.get("export") == "csv":
        if not has_perm("export.csv"):
            abort(403)
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["match_code", "kickoff", "home", "away", "venue", "status", "home_score", "away_score", "collector"])
        for r in rows:
            w.writerow([r["match_code"], r["kickoff"], r["home"], r["away"], r["venue"] or "", r["status"], r["home_score"], r["away_score"], r["collector"] or ""])
        audit("export.csv", "matches", None, {"rows": len(rows)})
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=matches.csv"})
    return render_template("matches/list.html", rows=rows, group=group, st=st, term=term, mine=mine,
                           group_title=GROUPS[group][0] if group in GROUPS else None, now=local_now().strftime("%Y-%m-%d %H:%M:%S"))


def _next_code():
    year = datetime.now().year
    n = scalar("SELECT COUNT(*) FROM matches WHERE match_code LIKE ?", (f"M-{year}-%",)) + 1
    while scalar("SELECT COUNT(*) FROM matches WHERE match_code=?", (f"M-{year}-{n:04d}",)):
        n += 1
    return f"M-{year}-{n:04d}"


def _assignments(mid):
    return {r["assignment_role"]: r["user_id"] for r in q("SELECT assignment_role, user_id FROM collection_assignments WHERE match_id=?", (mid,))}


def _set_assignment(mid, role, user_id, deadline):
    cur = q("SELECT * FROM collection_assignments WHERE match_id=? AND assignment_role=?", (mid, role), one=True)
    if user_id is None:
        if cur:
            ex("DELETE FROM collection_assignments WHERE id=?", (cur["id"],))
            audit("match.unassign", "matches", mid, {"role": role, "user": cur["user_id"]})
        return
    if cur and cur["user_id"] == user_id:
        ex("UPDATE collection_assignments SET deadline=? WHERE id=?", (deadline, cur["id"]))
        return
    if cur:
        ex("DELETE FROM collection_assignments WHERE id=?", (cur["id"],))
    ex("INSERT OR IGNORE INTO collection_assignments (match_id, user_id, assignment_role, deadline) VALUES (?,?,?,?)", (mid, user_id, role, deadline))
    audit("match.assign", "matches", mid, {"role": role, "user": user_id})
    ex("INSERT INTO tasks (title, description, assigned_to, department, priority, due_date, related_type, related_id, created_by) "
       "VALUES (?,?,?,?,?,?,?,?,?)",
       (f"{dict(ROLE_FIELDS)[role]} duty for match", "Assigned from the match record.", user_id,
        {"collector": "Operations", "backup_collector": "Operations", "analyst": "Analysis", "video_analyst": "Scouting"}[role],
        "normal", (deadline or "")[:10] or None, "match", mid, g.user["id"]))


def _form(m=None):
    fields = MATCH_FIELDS + ASSIGN_FIELDS
    cur_assign = _assignments(m["id"]) if m else {}
    if request.method == "POST":
        vals, errs = parse_form(fields, request.form)
        if vals.get("home_team_id") and vals.get("home_team_id") == vals.get("away_team_id"):
            errs["away_team_id"] = "Home and away team must be different."
        if vals.get("season_id") and vals.get("competition_id"):
            s = q("SELECT competition_id FROM seasons WHERE id=?", (vals["season_id"],), one=True)
            if s and s["competition_id"] != vals["competition_id"]:
                errs["season_id"] = "This season belongs to a different competition."
        if vals.get("duration_minutes") is not None and not (30 <= vals["duration_minutes"] <= 150):
            errs["duration_minutes"] = "Match length must be between 30 and 150 minutes."
        if errs:
            flash("Some details need attention.", "error")
            return render_template("matches/form.html", m=m, fields=fields, form=request.form, errs=errs, cur_assign=cur_assign), 422
        match_vals = {f.name: vals[f.name] for f in MATCH_FIELDS}
        if m:
            ex("UPDATE matches SET " + ", ".join(f"{k}=?" for k in match_vals) + ", updated_at=CURRENT_TIMESTAMP WHERE id=?",
               list(match_vals.values()) + [m["id"]])
            audit("matches.update", "matches", m["id"], diff(m, match_vals, list(match_vals)))
            mid = m["id"]
        else:
            code = _next_code()
            names = list(match_vals) + ["match_code", "created_by"]
            mid = ex(f"INSERT INTO matches ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                     list(match_vals.values()) + [code, g.user["id"]])
            for item in CHECKLIST_DEFAULT:
                ex("INSERT INTO match_checklist_items (match_id, label) VALUES (?,?)", (mid, item))
            ex("INSERT INTO match_status_history (match_id, old_status, new_status, user_id, note) VALUES (?,?,?,?,?)",
               (mid, None, "scheduled", g.user["id"], "Fixture created"))
            audit("matches.create", "matches", mid, {"code": code})
        for role, _label in ROLE_FIELDS:
            _set_assignment(mid, role, vals.get(f"as_{role}"), vals.get("collection_deadline"))
        cur = q("SELECT status FROM matches WHERE id=?", (mid,), one=True)["status"]
        if vals.get("as_collector") and cur == "scheduled":
            set_status(mid, "assigned", g.user["id"], "Collector assigned")
        flash("Fixture saved.", "ok")
        return redirect(url_for("matches.detail", mid=mid))
    return render_template("matches/form.html", m=m, fields=fields, form=None, errs={}, cur_assign=cur_assign)


@bp.route("/new", methods=["GET", "POST"])
@perm_required("match.manage")
def create():
    return _form(None)


@bp.route("/<int:mid>/edit", methods=["GET", "POST"])
@perm_required("match.manage")
def edit(mid):
    m = q("SELECT * FROM matches WHERE id=?", (mid,), one=True)
    if not m:
        abort(404)
    return _form(m)


@bp.route("/<int:mid>")
def detail(mid):
    m = match_row(mid)
    assigns = q("SELECT ca.*, u.full_name FROM collection_assignments ca JOIN users u ON u.id=ca.user_id WHERE ca.match_id=? ORDER BY ca.assignment_role", (mid,))
    checklist = q("SELECT c.*, u.full_name FROM match_checklist_items c LEFT JOIN users u ON u.id=c.done_by WHERE c.match_id=? ORDER BY c.id", (mid,))
    history = q("SELECT h.*, u.full_name FROM match_status_history h LEFT JOIN users u ON u.id=h.user_id WHERE h.match_id=? ORDER BY h.id DESC", (mid,))
    scope = {r["category"] for r in q("SELECT category FROM match_collection_scope WHERE match_id=? AND collected=1", (mid,))}
    counts = dict(
        events=scalar("SELECT COUNT(*) FROM match_events WHERE match_id=?", (mid,)),
        drafts=scalar("SELECT COUNT(*) FROM match_events WHERE match_id=? AND validation_status='draft'", (mid,)),
        home_squad=scalar("SELECT COUNT(*) FROM appearances WHERE match_id=? AND team_id=?", (mid, m["home_team_id"])),
        away_squad=scalar("SELECT COUNT(*) FROM appearances WHERE match_id=? AND team_id=?", (mid, m["away_team_id"])),
        open_errors=scalar("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND status='open' AND severity='error'", (mid,)),
        open_warnings=scalar("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND status='open' AND severity='warning'", (mid,)))
    reports = q("SELECT id, title, status, report_type FROM reports WHERE match_id=? ORDER BY id DESC", (mid,)) if has_perm("report.view") else []
    return render_template("matches/detail.html", m=m, assigns=assigns, checklist=checklist, history=history, scope=scope,
                           counts=counts, reports=reports, can_manage=has_perm("match.manage"), can_edit_collection=can_edit_collection(m),
                           can_collect_here=has_perm("events.collect") and can_collect(g.user["id"], mid),
                           manual_statuses=[(s, C.STATUS_LABEL[s]) for s in C.MANUAL_STATUSES],
                           now=local_now().strftime("%Y-%m-%d %H:%M:%S"))


@bp.route("/<int:mid>/status", methods=["POST"])
@perm_required("match.manage")
def change_status(mid):
    m = match_row(mid)
    new = request.form.get("status", "")
    if new not in C.MANUAL_STATUSES:
        abort(400, "That status can only be set by the workflow itself.")
    if m["status"] in C.VALIDATED_OR_LATER and new not in ("archived",):
        flash("Validated matches can only be archived here. Data changes must follow the correction process.", "error")
    elif m["status"] in ("data_submitted", "validation_required", "corrections_required") and new in ("scheduled", "assigned", "ready_for_collection"):
        flash("Data has been submitted for this match - use the validation queue to return it for correction.", "error")
    else:
        set_status(mid, new, g.user["id"], request.form.get("note", "")[:200])
        flash(f"Status changed to {C.STATUS_LABEL[new]}.", "ok")
    return redirect(url_for("matches.detail", mid=mid))


@bp.route("/<int:mid>/checklist/<int:iid>", methods=["POST"])
def toggle_check(mid, iid):
    m = match_row(mid)
    if not (has_perm("match.manage") or is_assigned(g.user["id"], mid)):
        abort(403)
    it = q("SELECT * FROM match_checklist_items WHERE id=? AND match_id=?", (iid, mid), one=True)
    if not it:
        abort(404)
    done = 0 if it["done"] else 1
    ex("UPDATE match_checklist_items SET done=?, done_by=?, done_at=CASE WHEN ?=1 THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?",
       (done, g.user["id"], done, iid))
    audit("match.checklist", "matches", mid, {"item": it["label"], "done": done})
    return redirect(url_for("matches.detail", mid=mid) + "#checklist")


@bp.route("/<int:mid>/checklist", methods=["POST"])
@perm_required("match.manage")
def add_check(mid):
    match_row(mid)
    label = request.form.get("label", "").strip()[:190]
    if label:
        ex("INSERT INTO match_checklist_items (match_id, label) VALUES (?,?)", (mid, label))
    return redirect(url_for("matches.detail", mid=mid) + "#checklist")


@bp.route("/<int:mid>/result", methods=["POST"])
def save_result(mid):
    m = match_row(mid)
    if not can_edit_collection(m):
        abort(403)
    fields = [F("home_score", "Home score", "int"), F("away_score", "Away score", "int"),
              F("score_source", "Score source"), F("attendance", "Attendance", "int"),
              F("possession_home", "Possession - home (%)", "number"), F("possession_away", "Possession - away (%)", "number"),
              F("possession_source", "Possession source")]
    vals, errs = parse_form(fields, request.form)
    for k in ("home_score", "away_score", "attendance"):
        if vals.get(k) is not None and vals[k] < 0:
            errs[k] = "Cannot be negative."
    if (vals.get("home_score") is None) != (vals.get("away_score") is None):
        errs["home_score"] = "Enter both scores or neither."
    ph, pa = vals.get("possession_home"), vals.get("possession_away")
    if (ph is not None or pa is not None) and not vals.get("possession_source"):
        errs["possession_source"] = "Possession is only stored with a documented source or method."
    if ph is not None and pa is not None and abs(ph + pa - 100) > 1.5:
        errs["possession_home"] = "Possession values should add up to about 100%."
    if errs:
        flash(" ".join(errs.values()), "error")
    else:
        ex("UPDATE matches SET " + ", ".join(f"{k}=?" for k in vals) + ", updated_at=CURRENT_TIMESTAMP WHERE id=?", list(vals.values()) + [mid])
        audit("match.result", "matches", mid, diff(m, vals, list(vals)))
        flash("Official result saved.", "ok")
    return redirect(url_for("matches.detail", mid=mid) + "#result")


@bp.route("/<int:mid>/scope", methods=["POST"])
def save_scope(mid):
    m = match_row(mid)
    if not can_edit_collection(m):
        abort(403)
    chosen = set(request.form.getlist("scope"))
    for cat, _ in C.SCOPE_CATEGORIES:
        ex("INSERT INTO match_collection_scope (match_id, category, collected) VALUES (?,?,?) "
           "ON CONFLICT(match_id, category) DO UPDATE SET collected=excluded.collected", (mid, cat, 1 if cat in chosen else 0))
    audit("match.scope", "matches", mid, {"collected": sorted(chosen)})
    flash("Collection scope saved. Categories left unticked will show as 'Not collected' in reports.", "ok")
    return redirect(url_for("matches.detail", mid=mid) + "#scope")


# ----------------------------------------------------------------------------- lineups
def _roster(m, team_id):
    return q("SELECT DISTINCT p.id, p.full_name, p.position, p.shirt_number AS cur_shirt FROM players p WHERE p.current_team_id=? "
             "OR p.id IN (SELECT player_id FROM player_team_history WHERE team_id=?) "
             "OR p.id IN (SELECT player_id FROM match_squads WHERE match_id=? AND team_id=?) ORDER BY p.full_name",
             (team_id, team_id, m["id"], team_id))


def _lineup_rows(m, team_id):
    sq = {r["player_id"]: dict(r) for r in q("SELECT * FROM match_squads WHERE match_id=? AND team_id=?", (m["id"], team_id))}
    ap = {r["player_id"]: dict(r) for r in q("SELECT * FROM appearances WHERE match_id=? AND team_id=?", (m["id"], team_id))}
    rows = []
    for p in _roster(m, team_id):
        s, a = sq.get(p["id"]), ap.get(p["id"])
        rows.append(dict(p=dict(p), s=s, a=a, inc=s is not None))
    return rows


@bp.route("/<int:mid>/lineups", methods=["GET", "POST"])
def lineups(mid):
    m = match_row(mid)
    if not (has_perm("squad.edit", "events.correct", "events.view", "events.collect")):
        abort(403)
    editable = can_edit_collection(m)
    errors = []
    if request.method == "POST":
        if not editable:
            abort(403)
        team_id = request.form.get("team_id", type=int)
        if team_id not in (m["home_team_id"], m["away_team_id"]):
            abort(400, "Team is not part of this match.")
        roster = _roster(m, team_id)
        can_verify = has_perm("events.validate")
        todo = []
        for p in roster:
            k = f"p{p['id']}_"
            if not request.form.get(k + "in"):
                todo.append((p["id"], None))
                continue
            def num(name, lo=0, hi=150):
                raw = request.form.get(k + name, "").strip()
                if raw == "":
                    return None
                try:
                    v = int(raw)
                except ValueError:
                    errors.append(f"{p['full_name']}: {name.replace('_', ' ')} must be a whole number.")
                    return None
                if not lo <= v <= hi:
                    errors.append(f"{p['full_name']}: {name.replace('_', ' ')} must be between {lo} and {hi}.")
                return v
            starter = 1 if request.form.get(k + "starter") else 0
            d = dict(shirt=num("shirt", 0, 99), pos=request.form.get(k + "pos", "")[:40] or None, starter=starter,
                     on=num("on"), off=num("off"), dis=num("dis"),
                     status=request.form.get(k + "status", "played"), unc=1 if request.form.get(k + "unc") else 0,
                     ver=request.form.get(k + "ver", "unverified"))
            if d["status"] not in ("played", "unused_substitute", "did_not_play", "unknown"):
                errors.append(f"{p['full_name']}: invalid appearance status.")
            if starter and d["on"] is not None:
                errors.append(f"{p['full_name']}: a starter cannot have a substitution-on minute.")
            if d["on"] is not None and d["off"] is not None and d["off"] <= d["on"]:
                errors.append(f"{p['full_name']}: substitution-off minute must be after the on minute.")
            if d["status"] == "played" and not starter and d["on"] is None and not d["unc"]:
                errors.append(f"{p['full_name']}: substitute marked as played needs a substitution-on minute (or tick 'minutes uncertain').")
            if d["ver"] not in ("unverified", "verified"):
                d["ver"] = "unverified"
            todo.append((p["id"], d))
        n_start = sum(1 for _, d in todo if d and d["starter"])
        if n_start > 11:
            errors.append(f"{n_start} starters selected - a team can start with at most 11 players.")
        if not errors:
            for pid, d in todo:
                if d is None:
                    if scalar("SELECT COUNT(*) FROM match_events WHERE match_id=? AND (player_id=? OR related_player_id=?)", (mid, pid, pid)):
                        if scalar("SELECT COUNT(*) FROM match_squads WHERE match_id=? AND player_id=?", (mid, pid)):
                            errors.append("A player with recorded events cannot be removed from the lineup.")
                        continue
                    ex("DELETE FROM appearances WHERE match_id=? AND player_id=?", (mid, pid))
                    ex("DELETE FROM match_squads WHERE match_id=? AND player_id=?", (mid, pid))
                    continue
                ex("INSERT INTO match_squads (match_id, team_id, player_id, shirt_number, is_starter, position) VALUES (?,?,?,?,?,?) "
                   "ON CONFLICT(match_id, player_id) DO UPDATE SET shirt_number=excluded.shirt_number, is_starter=excluded.is_starter, position=excluded.position",
                   (mid, team_id, pid, d["shirt"], d["starter"], d["pos"]))
                prev = q("SELECT verification_status FROM appearances WHERE match_id=? AND player_id=?", (mid, pid), one=True)
                ver = d["ver"] if can_verify else (prev["verification_status"] if prev else "unverified")
                ex("INSERT INTO appearances (match_id, team_id, player_id, role, start_position, sub_on_minute, sub_off_minute, dismissed_minute, "
                   "appearance_status, minutes_uncertain, source_id, verification_status) VALUES (?,?,?,?,?,?,?,?,?,?,1,?) "
                   "ON CONFLICT(match_id, player_id) DO UPDATE SET role=excluded.role, start_position=excluded.start_position, "
                   "sub_on_minute=excluded.sub_on_minute, sub_off_minute=excluded.sub_off_minute, dismissed_minute=excluded.dismissed_minute, "
                   "appearance_status=excluded.appearance_status, minutes_uncertain=excluded.minutes_uncertain, verification_status=excluded.verification_status",
                   (mid, team_id, pid, "starter" if d["starter"] else "substitute", d["pos"], d["on"], d["off"], d["dis"], d["status"], d["unc"], ver))
        if errors:
            g.db.rollback()
            for e in errors:
                flash(e, "error")
        else:
            audit("match.lineup", "matches", mid, {"team": team_id, "players": sum(1 for _, d in todo if d)})
            if m["status"] in C.VALIDATED_OR_LATER:
                audit("match.lineup.post_validation_change", "matches", mid, {"team": team_id})
            flash("Lineup and appearances saved.", "ok")
            return redirect(url_for("matches.lineups", mid=mid) + f"#team{team_id}")
    teams = []
    for tid, name in ((m["home_team_id"], m["home"]), (m["away_team_id"], m["away"])):
        teams.append(dict(id=tid, name=name, rows=_lineup_rows(m, tid)))
    others = q("SELECT id, full_name FROM players ORDER BY full_name") if editable else []
    return render_template("matches/lineups.html", m=m, teams=teams, editable=editable, others=others,
                           can_verify=has_perm("events.validate"), form=request.form if errors else None)


@bp.route("/<int:mid>/lineups/add", methods=["POST"])
def lineup_add(mid):
    m = match_row(mid)
    if not can_edit_collection(m):
        abort(403)
    tid, pid = request.form.get("team_id", type=int), request.form.get("player_id", type=int)
    if tid not in (m["home_team_id"], m["away_team_id"]) or not scalar("SELECT COUNT(*) FROM players WHERE id=?", (pid,)):
        abort(400, "Choose a player and one of the two teams.")
    if scalar("SELECT COUNT(*) FROM match_squads WHERE match_id=? AND player_id=?", (mid, pid)):
        flash("That player is already in a squad for this match.", "error")
    else:
        ex("INSERT INTO match_squads (match_id, team_id, player_id, is_starter) VALUES (?,?,?,0)", (mid, tid, pid))
        flash("Player added to the squad - complete their appearance details below.", "ok")
        audit("match.squad_add", "matches", mid, {"team": tid, "player": pid})
    return redirect(url_for("matches.lineups", mid=mid) + f"#team{tid}")
