"""Mobile-friendly match event collection: quick entry, drafts, duplicate detection, submission and CSV fallback."""
import csv
import io

from flask import Blueprint, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .. import constants as C
from ..db import ex, q, scalar
from ..security import audit, has_perm, perm_required
from ..workflow import can_collect, set_status
from .matches import can_edit_collection, match_row

bp = Blueprint("collect", __name__, url_prefix="/collect")

CSV_COLUMNS = ["team", "player", "event_type", "period", "minute", "second", "outcome", "related_player",
               "set_piece_type", "x_start", "y_start", "x_end", "y_end", "video_timestamp", "notes"]


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client":
        abort(403)


def _may_enter(m, event=None):
    """Collectors enter events only for their assigned matches and only before validation; validators may correct."""
    if m["status"] in C.VALIDATED_OR_LATER:
        return False
    if has_perm("events.correct"):
        return True
    if m["status"] not in C.PRE_SUBMISSION:           # submitted data is locked for the collector until it is returned
        return False
    return has_perm("events.collect") and can_collect(g.user["id"], m["id"])


def _types():
    return {r["id"]: dict(r) for r in q("SELECT * FROM event_types WHERE is_active=1 ORDER BY sort_order")}


def _validate_event(m, data, types):
    """Server-side checks for one event. Returns (clean dict, errors list)."""
    errs, d = [], {}
    t = types.get(data.get("event_type_id"))
    if not t:
        return d, ["Choose an event type."]
    d["event_type_id"] = t["id"]
    team = data.get("team_id")
    if team not in (m["home_team_id"], m["away_team_id"]):
        errs.append("The team is not playing in this match.")
    d["team_id"] = team
    period = data.get("period")
    if period not in [p for p, _ in C.PERIODS]:
        errs.append("Choose a match period.")
    d["period"] = period
    minute, second = data.get("minute"), data.get("second")
    if minute is None:
        errs.append("Enter the match minute.")
    elif not 0 <= minute <= 150:
        errs.append("Minute must be between 0 and 150.")
    if second is not None and not 0 <= second <= 59:
        errs.append("Second must be between 0 and 59.")
    d["minute"], d["second"] = minute, second
    pid = data.get("player_id")
    if t["needs_player"] and not pid:
        errs.append(f"Choose the player for this {t['name'].lower()}.")
    if pid:
        a = q("SELECT team_id FROM appearances WHERE match_id=? AND player_id=?", (m["id"], pid), one=True)
        s = q("SELECT team_id FROM match_squads WHERE match_id=? AND player_id=?", (m["id"], pid), one=True)
        row = a or s
        if not row:
            errs.append("That player is not in the lineup for this match - add them in Lineups first.")
        elif row["team_id"] != team and t["code"] != "own_goal":
            errs.append("That player belongs to the other team in this match.")
        elif t["code"] == "own_goal" and row["team_id"] != team:
            errs.append("For an own goal, select the team of the player who scored it.")
    d["player_id"] = pid
    rel = data.get("related_player_id")
    if rel:
        if not scalar("SELECT COUNT(*) FROM appearances WHERE match_id=? AND player_id=?", (m["id"], rel)) and \
                not scalar("SELECT COUNT(*) FROM match_squads WHERE match_id=? AND player_id=?", (m["id"], rel)):
            errs.append("The related player is not in the lineup for this match.")
        if rel == pid:
            errs.append("The related player cannot be the same as the main player.")
    d["related_player_id"] = rel
    outcome = data.get("outcome")
    allowed = [o for o in (t["outcomes"] or "").split(",") if o]
    if allowed:
        if not outcome:
            errs.append("Choose the outcome.")
        elif outcome not in allowed:
            errs.append("Invalid outcome for this event type.")
    else:
        outcome = None
    d["outcome"] = outcome
    sp = data.get("set_piece_type") if t["uses_set_piece"] else None
    if sp and sp not in C.SET_PIECE_TYPES:
        errs.append("Invalid set-piece type.")
    d["set_piece_type"] = sp or None
    for k in ("x_start", "y_start", "x_end", "y_end"):
        v = data.get(k)
        if v is not None and not 0 <= v <= 100:
            errs.append("Pitch coordinates must be between 0 and 100.")
        d[k] = v if t["uses_coords"] != "none" and (t["uses_coords"] == "start_end" or k.endswith("start")) else None
    d["video_timestamp"] = data.get("video_timestamp")
    d["notes"] = (data.get("notes") or "")[:1000] or None
    return d, errs


def _dup(mid, d, exclude_id=None):
    if d.get("minute") is None:
        return None
    sql = ("SELECT id FROM match_events WHERE match_id=? AND event_type_id=? AND team_id=? AND COALESCE(player_id,0)=COALESCE(?,0) "
           "AND period=? AND minute=? AND COALESCE(second,-1)=COALESCE(?,-1) AND COALESCE(outcome,'')=COALESCE(?,'')")
    args = [mid, d["event_type_id"], d["team_id"], d["player_id"], d["period"], d["minute"], d["second"], d["outcome"]]
    if exclude_id:
        sql += " AND id != ?"
        args.append(exclude_id)
    r = q(sql, args, one=True)
    return r["id"] if r else None


def _num(v, cast=float):
    try:
        return cast(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


@bp.route("/")
def my_matches():
    rows = q("SELECT m.id, m.match_code, m.kickoff, m.status, m.collection_deadline, ht.name AS home, at.name AS away, ca.assignment_role, "
             "(SELECT COUNT(*) FROM match_events e WHERE e.match_id=m.id) AS n_events FROM collection_assignments ca "
             "JOIN matches m ON m.id=ca.match_id JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
             "WHERE ca.user_id=? AND ca.assignment_role IN ('collector','backup_collector') AND m.status NOT IN ('archived','cancelled') "
             "ORDER BY m.kickoff", (g.user["id"],))
    if not (has_perm("events.collect") or has_perm("events.correct")):
        abort(403)
    return render_template("collect/my_matches.html", rows=rows)


@bp.route("/<int:mid>")
def entry(mid):
    m = match_row(mid)
    if not (has_perm("events.view", "events.collect")):
        abort(403)
    types = _types()
    editable = _may_enter(m)
    teams = {m["home_team_id"]: m["home"], m["away_team_id"]: m["away"]}
    players = q("SELECT a.player_id, a.team_id, p.full_name, COALESCE(s.shirt_number, p.shirt_number) AS shirt, a.role, a.appearance_status "
                "FROM appearances a JOIN players p ON p.id=a.player_id LEFT JOIN match_squads s ON s.match_id=a.match_id AND s.player_id=a.player_id "
                "WHERE a.match_id=? ORDER BY a.team_id, CASE a.role WHEN 'starter' THEN 0 ELSE 1 END, COALESCE(s.shirt_number, 99), p.full_name", (mid,))
    scope = {r["category"] for r in q("SELECT category FROM match_collection_scope WHERE match_id=? AND collected=1", (mid,))}
    events = q("SELECT e.*, t.name AS type_name, t.code, p.full_name AS player, rp.full_name AS related FROM match_events e "
               "JOIN event_types t ON t.id=e.event_type_id LEFT JOIN players p ON p.id=e.player_id LEFT JOIN players rp ON rp.id=e.related_player_id "
               "WHERE e.match_id=? ORDER BY e.id DESC LIMIT 40", (mid,))
    counts = dict(total=scalar("SELECT COUNT(*) FROM match_events WHERE match_id=?", (mid,)),
                  draft=scalar("SELECT COUNT(*) FROM match_events WHERE match_id=? AND validation_status='draft'", (mid,)))
    import json as _json
    all_events = q("SELECT * FROM match_events WHERE match_id=? ORDER BY id DESC LIMIT 40", (mid,))
    cfg = _json.dumps(dict(mid=mid, csrf=__import__("flask").session.get("_csrf"),
                           types=[dict(id=t["id"], code=t["code"], name=t["name"], category=t["category"], outcomes=[o for o in (t["outcomes"] or "").split(",") if o],
                                       needs_player=bool(t["needs_player"]), related_label=t["related_label"], coords=t["uses_coords"], set_piece=bool(t["uses_set_piece"])) for t in types.values()],
                           players=[dict(id=p["player_id"], team=p["team_id"], name=p["full_name"], shirt=p["shirt"], role=p["role"], status=p["appearance_status"]) for p in players],
                           teams={str(k): v for k, v in teams.items()},
                           events={str(e["id"]): {k: e[k] for k in e.keys()} for e in all_events})).replace("<", "\\u003c")
    return render_template("collect/entry.html", cfg=cfg, m=m, types=list(types.values()), editable=editable, teams=teams, players=players,
                           scope=scope, events=events, counts=counts, periods=C.PERIODS, set_pieces=C.SET_PIECE_TYPES,
                           can_submit=editable and m["status"] in C.PRE_SUBMISSION, can_correct=has_perm("events.correct"),
                           lineup_ready=len({p["team_id"] for p in players}) == 2)


@bp.route("/<int:mid>/event", methods=["POST"])
def save_event(mid):
    """JSON endpoint used by the mobile form. Creates a draft event, or updates one (with a reason when correcting)."""
    m = match_row(mid)
    if not _may_enter(m):
        return jsonify(ok=False, errors=["You cannot record events for this match (not assigned, or data already validated)."]), 403
    j = request.get_json(silent=True) or {}
    types = _types()
    data = dict(event_type_id=_num(j.get("event_type_id"), int), team_id=_num(j.get("team_id"), int), period=j.get("period"),
                minute=_num(j.get("minute"), int), second=_num(j.get("second"), int), player_id=_num(j.get("player_id"), int),
                related_player_id=_num(j.get("related_player_id"), int), outcome=j.get("outcome") or None,
                set_piece_type=j.get("set_piece_type") or None, x_start=_num(j.get("x_start")), y_start=_num(j.get("y_start")),
                x_end=_num(j.get("x_end")), y_end=_num(j.get("y_end")), video_timestamp=_num(j.get("video_timestamp"), int),
                notes=j.get("notes"))
    d, errs = _validate_event(m, data, types)
    eid = _num(j.get("id"), int)
    old = q("SELECT * FROM match_events WHERE id=? AND match_id=?", (eid, mid), one=True) if eid else None
    if eid and not old:
        return jsonify(ok=False, errors=["Event not found."]), 404
    if old:
        own_draft = old["collector_id"] == g.user["id"] and old["validation_status"] in ("draft", "returned")
        if not (own_draft or has_perm("events.correct")):
            return jsonify(ok=False, errors=["You can only edit your own draft events."]), 403
        reason = (j.get("reason") or "").strip()
        if old["validation_status"] not in ("draft",) and not reason:
            errs.append("A reason is required when correcting a submitted event.")
    if errs:
        return jsonify(ok=False, errors=errs), 422
    dup = _dup(mid, d, eid)
    if dup and not j.get("confirm_duplicate"):
        return jsonify(ok=False, duplicate=True, errors=[f"This looks like a duplicate of event #{dup} (same type, player and time)."]), 409
    cols = ["event_type_id", "team_id", "player_id", "period", "minute", "second", "outcome", "related_player_id", "set_piece_type",
            "x_start", "y_start", "x_end", "y_end", "video_timestamp", "notes"]
    if old:
        ex("UPDATE match_events SET " + ", ".join(f"{c}=?" for c in cols) + ", correction_reason=?, modified_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
           [d.get(c) for c in cols] + [(j.get("reason") or None), g.user["id"], eid])
        audit("event.correct", "match_events", eid, {"reason": j.get("reason"), "before": {c: old[c] for c in cols if old[c] != d.get(c)},
                                                      "after": {c: d.get(c) for c in cols if old[c] != d.get(c)}})
        new_id = eid
    else:
        new_id = ex("INSERT INTO match_events (match_id, " + ", ".join(cols) + ", collector_id, source_id, validation_status) VALUES (?," +
                    ",".join("?" * len(cols)) + ",?,1,'draft')", [mid] + [d.get(c) for c in cols] + [g.user["id"]])
        if m["status"] in ("assigned", "ready_for_collection", "scheduled"):
            set_status(mid, "collection_in_progress", g.user["id"], "First event recorded")
    return jsonify(ok=True, id=new_id, message="Saved as draft." if not old else "Correction saved and logged.")


@bp.route("/<int:mid>/event/<int:eid>/delete", methods=["POST"])
def delete_event(mid, eid):
    m = match_row(mid)
    ev = q("SELECT * FROM match_events WHERE id=? AND match_id=?", (eid, mid), one=True)
    if not ev:
        abort(404)
    if not _may_enter(m) or not ((ev["collector_id"] == g.user["id"] and ev["validation_status"] == "draft") or has_perm("events.correct")):
        abort(403)
    reason = request.form.get("reason", "").strip()
    if ev["validation_status"] != "draft" and not reason:
        flash("A reason is required to delete a submitted event.", "error")
    else:
        ex("DELETE FROM match_events WHERE id=?", (eid,))
        audit("event.delete", "match_events", eid, {"reason": reason, "event": {k: ev[k] for k in ev.keys()}})
        flash("Event deleted.", "ok")
    return redirect(url_for("collect.entry", mid=mid))


@bp.route("/<int:mid>/submit", methods=["POST"])
def submit(mid):
    m = match_row(mid)
    if not (_may_enter(m) and m["status"] in C.PRE_SUBMISSION):
        abort(403)
    problems = []
    if not scalar("SELECT COUNT(*) FROM match_collection_scope WHERE match_id=? AND collected=1", (mid,)):
        problems.append("Declare which event categories you collected (Match page - Collection scope).")
    if m["home_score"] is None or m["away_score"] is None:
        problems.append("Enter the official final score (Match page - Official result).")
    for tid in (m["home_team_id"], m["away_team_id"]):
        if not scalar("SELECT COUNT(*) FROM appearances WHERE match_id=? AND team_id=?", (mid, tid)):
            problems.append("Lineups are missing for one of the teams.")
            break
    if not scalar("SELECT COUNT(*) FROM match_events WHERE match_id=?", (mid,)):
        problems.append("No events have been recorded.")
    if problems:
        for p in problems:
            flash(p, "error")
        return redirect(url_for("collect.entry", mid=mid))
    n = ex("UPDATE match_events SET validation_status='submitted', updated_at=CURRENT_TIMESTAMP WHERE match_id=? AND validation_status IN ('draft','returned')", (mid,))
    cnt = scalar("SELECT COUNT(*) FROM match_events WHERE match_id=? AND validation_status='submitted'", (mid,))
    set_status(mid, "data_submitted", g.user["id"], f"{cnt} events submitted")
    set_status(mid, "validation_required", g.user["id"], "Awaiting validation")
    ex("UPDATE collection_assignments SET status='submitted' WHERE match_id=? AND user_id=?", (mid, g.user["id"]))
    from ..workflow import run_validation
    run_validation(mid)
    audit("match.submit", "matches", mid, {"events": cnt})
    flash(f"{cnt} events submitted for validation.", "ok")
    return redirect(url_for("matches.detail", mid=mid))


# ----------------------------------------------------------------------------- CSV fallback
@bp.route("/<int:mid>/template.csv")
def csv_template(mid):
    match_row(mid)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    m = match_row(mid)
    w.writerow([m["home"], "Example Player Name", "pass", "1H", 12, 30, "completed", "", "", 30, 40, 45, 50, "", "example row - delete"])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=events_{m['match_code']}_template.csv"})


@bp.route("/<int:mid>/import", methods=["POST"])
def csv_import(mid):
    """Paper/CSV fallback when connectivity fails. All-or-nothing: any invalid row rejects the whole file."""
    m = match_row(mid)
    if not _may_enter(m):
        abort(403)
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"):
        flash("Choose a .csv file (use the template).", "error")
        return redirect(url_for("collect.entry", mid=mid))
    try:
        text = f.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("The file must be UTF-8 text (save as CSV UTF-8).", "error")
        return redirect(url_for("collect.entry", mid=mid))
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in ("team", "player", "event_type", "period", "minute") if c not in (reader.fieldnames or [])]
    if missing:
        flash("Missing columns: " + ", ".join(missing), "error")
        return redirect(url_for("collect.entry", mid=mid))
    types_by_code = {t["code"]: t for t in _types().values()}
    types_by_name = {t["name"].lower(): t for t in _types().values()}
    teams = {m["home"].lower(): m["home_team_id"], m["away"].lower(): m["away_team_id"],
             "home": m["home_team_id"], "away": m["away_team_id"]}
    plist = {r["full_name"].lower(): r["player_id"] for r in q("SELECT a.player_id, p.full_name FROM appearances a JOIN players p ON p.id=a.player_id WHERE a.match_id=?", (mid,))}
    types = _types()
    good, bad = [], []
    rows = list(reader)
    for i, r in enumerate(rows, start=2):
        r = {k: (v or "").strip() for k, v in r.items() if k}
        if not any(r.values()) or r.get("notes", "").startswith("example row"):
            continue
        t = types_by_code.get(r["event_type"].lower().replace(" ", "_")) or types_by_name.get(r["event_type"].lower())
        data = dict(event_type_id=t["id"] if t else None, team_id=teams.get(r["team"].lower()), period=r["period"].upper(),
                    minute=_num(r["minute"], int), second=_num(r.get("second"), int),
                    player_id=plist.get(r["player"].lower()) if r["player"] else None,
                    related_player_id=plist.get(r.get("related_player", "").lower()) if r.get("related_player") else None,
                    outcome=r.get("outcome") or None, set_piece_type=r.get("set_piece_type") or None,
                    x_start=_num(r.get("x_start")), y_start=_num(r.get("y_start")), x_end=_num(r.get("x_end")), y_end=_num(r.get("y_end")),
                    video_timestamp=_num(r.get("video_timestamp"), int), notes=r.get("notes"))
        if r["player"] and data["player_id"] is None:
            bad.append(f"Row {i}: player '{r['player']}' is not in this match's lineup.")
            continue
        d, errs = _validate_event(m, data, types)
        if errs:
            bad.append(f"Row {i}: " + " ".join(errs))
        else:
            good.append(d)
    job = ex("INSERT INTO import_jobs (job_type, filename, status, rows_total, rows_ok, rows_failed, errors, user_id, match_id) VALUES (?,?,?,?,?,?,?,?,?)",
             ("events_csv", f.filename[:200], "failed" if bad else "complete", len(good) + len(bad), 0 if bad else len(good), len(bad),
              "\n".join(bad)[:4000] or None, g.user["id"], mid))
    if bad:
        for b in bad[:12]:
            flash(b, "error")
        flash(f"Nothing was imported: {len(bad)} row(s) need fixing. Correct the file and upload it again.", "error")
        return redirect(url_for("collect.entry", mid=mid))
    cols = ["event_type_id", "team_id", "player_id", "period", "minute", "second", "outcome", "related_player_id", "set_piece_type",
            "x_start", "y_start", "x_end", "y_end", "video_timestamp", "notes"]
    for d in good:
        ex("INSERT INTO match_events (match_id, " + ", ".join(cols) + ", collector_id, source_id, validation_status) VALUES (?," +
           ",".join("?" * len(cols)) + ",?,1,'draft')", [mid] + [d.get(c) for c in cols] + [g.user["id"]])
    if m["status"] in ("assigned", "ready_for_collection", "scheduled"):
        set_status(mid, "collection_in_progress", g.user["id"], "CSV import")
    audit("events.csv_import", "matches", mid, {"rows": len(good), "job": job})
    flash(f"{len(good)} events imported as drafts. Review them, then submit.", "ok")
    return redirect(url_for("collect.entry", mid=mid))
