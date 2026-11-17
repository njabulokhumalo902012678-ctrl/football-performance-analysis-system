"""Report generator: player, match, team and scouting reports with review, approval, versioning, PDF and client sharing."""
import base64
import json
from pathlib import Path

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request,
                   send_file, url_for)

from .. import charts, constants as C, pdfgen
from ..db import ex, get_setting, local_now, q, scalar
from ..metrics import analyse_match, fmt, minutes_played, store_run
from ..security import audit, has_perm, perm_required
from ..workflow import set_status

bp = Blueprint("reports", __name__, url_prefix="/reports")
TYPES = {"player": "Player performance report", "match": "Match analysis report", "team": "Team report", "scouting": "Scouting report"}
INPUT_LISTS = {
    "player": ["observations", "strengths", "development", "training", "next_match"],
    "match": ["insights", "tactical", "strengths", "weaknesses", "training", "next_match", "incidents"],
    "team": ["insights", "tactical", "strengths", "weaknesses", "training", "next_match", "incidents"],
    "scouting": [],
}
LIST_LABELS = {"observations": "Analyst observations", "strengths": "Strengths demonstrated", "development": "Development areas",
               "training": "Training priorities", "next_match": "Recommendations for the next match", "insights": "Key insights",
               "tactical": "Tactical observations", "weaknesses": "Weaknesses", "incidents": "Set pieces and important incidents"}


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client" or not has_perm("report.view", "report.create", "report.approve"):
        abort(403)


def _report(rid):
    r = q("SELECT r.*, u.full_name AS author, c.name AS client, m.match_code, m.status AS match_status FROM reports r "
          "LEFT JOIN users u ON u.id=r.created_by LEFT JOIN clients c ON c.id=r.client_id LEFT JOIN matches m ON m.id=r.match_id WHERE r.id=?", (rid,), one=True)
    if not r:
        abort(404)
    return r


def _content(r):
    try:
        return json.loads(r["content"] or "{}")
    except ValueError:
        return {}


def _is_owner(r):
    return r["created_by"] == g.user["id"]


def _lines(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()][:40]


# ----------------------------------------------------------------------------- snapshot
def _ev_text(e, names):
    p = names.get(e["player_id"], "Unknown")
    rel = names.get(e["related_player_id"]) if e["related_player_id"] else None
    c = e["code"]
    if c == "goal":
        return "goal", "Goal", f"Goal - {p}" + (f" (assist: {rel})" if rel else "") + (f" from {e['set_piece_type'].replace('_', ' ')}" if e["set_piece_type"] else "")
    if c == "penalty" and e["outcome"] == "scored":
        return "penalty", "Pen", f"Penalty scored - {p}"
    if c == "own_goal":
        return "own_goal", "OG", f"Own goal - {p}"
    if c == "card":
        red = e["outcome"] in ("red", "second_yellow")
        return ("card_r" if red else "card_y"), ("Red" if red else "Yellow"), f"{(e['outcome'] or '').replace('_', ' ').capitalize()} card - {p}"
    if c == "substitution":
        return "sub", "Sub", f"Substitution - {p} off" + (f", {rel} on" if rel else "")
    return None


def build_snapshot(r, version=None):
    content = _content(r)
    inp = content.get("input", {})
    s = dict(report_type=r["report_type"], title=r["title"], company=get_setting("company_name"), tagline=get_setting("company_tagline"),
             confidentiality=get_setting("confidentiality_statement"), confidential_short="Confidential - prepared for " + (r["client"] or "the named client"),
             client=r["client"], analyst=r["author"] or "Analyst", report_date=local_now().strftime("%d %B %Y"), version=version or "draft", input=inp)
    if r["report_type"] == "scouting":
        return _scouting_snapshot(r, s)
    m = q("SELECT m.*, ht.name AS home, at.name AS away, v.name AS venue, c.name AS competition FROM matches m "
          "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id LEFT JOIN venues v ON v.id=m.venue_id "
          "LEFT JOIN competitions c ON c.id=m.competition_id WHERE m.id=?", (r["match_id"],), one=True)
    prov = r["data_status"] == "provisional"
    res = analyse_match(m["id"], provisional=prov)
    md = res["match_data"]
    names = {x["id"]: x["full_name"] for x in q("SELECT id, full_name FROM players")}
    valid = m["status"] in C.VALIDATED_OR_LATER
    s["data_status"] = "validated" if (valid and not prov) or valid else "provisional"
    src = q("SELECT name, permission_status FROM data_sources WHERE id=1", one=True)
    s["source_name"] = f"{src['name']} ({src['permission_status'].replace('_', ' ')})" if src else "Not recorded"
    dt = str(m["kickoff"])[:10]
    s["match"] = dict(id=m["id"], code=m["match_code"], home=m["home"], away=m["away"], home_id=m["home_team_id"], away_id=m["away_team_id"],
                      home_score=m["home_score"], away_score=m["away_score"], competition=m["competition"], venue=m["venue"],
                      date=local_dt(m["kickoff"]), attendance=m["attendance"], duration=m["duration_minutes"], focus_team_id=r["team_id"])
    s["header_title"] = {"player": "Player performance analysis report", "match": "Match analysis report", "team": "Team analysis report"}[r["report_type"]]
    score = f"{m['home_score']} - {m['away_score']}" if m["home_score"] is not None else "v"
    s["report_kind"] = TYPES[r["report_type"]]
    s["team_stats"] = {"home": res["teams"][m["home_team_id"]], "away": res["teams"][m["away_team_id"]]}
    timeline, match_events = [], []
    for e in md["events"]:
        t = _ev_text(e, names)
        if t:
            kind, short, text = t
            timeline.append(dict(minute=e["minute"], kind=kind, short=short))
            match_events.append(dict(minute=e["minute"], kind=kind, text=text, team_id=e["team_id"]))
    s["timeline"], s["match_events"] = timeline, match_events
    s["quality"] = [t for lvl, t in res["quality"] if lvl in ("warning", "error")]
    bad = [lvl for lvl, _ in res["quality"] if lvl in ("warning", "error")]
    s["confidence"] = ("Low - provisional data" if s["data_status"] == "provisional" else
                       "Medium - validated, with data limitations" if bad else "High - validated data, confirmed lineups and minutes")
    if r["report_type"] == "player":
        pid = r["player_id"]
        if pid not in res["players"]:
            raise ValueError("The player has no appearance record in this match.")
        p = q("SELECT p.*, t.name AS team FROM players p LEFT JOIN teams t ON t.id=p.current_team_id WHERE p.id=?", (pid,), one=True)
        a = md["appearances"][pid]
        shirt = q("SELECT shirt_number FROM match_squads WHERE match_id=? AND player_id=?", (m["id"], pid), one=True)
        team_name = m["home"] if a["team_id"] == m["home_team_id"] else m["away"]
        s["player"] = dict(name=p["full_name"], position=a["start_position"] or p["position"], team=team_name, nationality=p["nationality"],
                           shirt=p["shirt_number"], verification=p["verification_status"], source=p["profile_source"], last_verified=p["date_last_verified"],
                           dob=p["date_of_birth"] if p["dob_authorised"] else None)
        s["appearance"] = dict(role=a["role"], sub_on_minute=a["sub_on_minute"], sub_off_minute=a["sub_off_minute"], shirt=shirt["shirt_number"] if shirt else None)
        s["stats"] = res["players"][pid]
        s["header_main"] = f"{p['full_name']}"
        s["header_sub"] = f"{s['player']['position'] or ''}  |  {team_name}"
        s["header_meta"] = [("Match", f"{m['home']} {score} {m['away']}"), ("Date", dt), ("Competition", m["competition"] or "-"), ("Client", r["client"] or "-")]
        s["player_events"] = []
        for e in md["events"]:
            if e["player_id"] == pid or e["related_player_id"] == pid:
                t = _ev_text(e, names)
                if t and (e["player_id"] == pid or t[0] in ("goal",)):
                    txt = t[2] if e["player_id"] == pid else f"Assist for {names.get(e['player_id'])}'s goal"
                    s["player_events"].append(dict(minute=e["minute"], kind=t[0] if e["player_id"] == pid else "assist", text=txt))
        mine = [e for e in md["events"] if e["player_id"] == pid]
        png = charts.shot_map(mine, a["team_id"], f"{p['full_name']} - shots")
        if png:
            s["shot_map_b64"] = base64.b64encode(png).decode()
        hp = charts.heatmap(md["events"], a["team_id"], f"{p['full_name']}", player_id=pid)
        if hp:
            s["heat_b64"] = base64.b64encode(hp).decode()
        s["video"] = _video_for(r, pid)
    else:
        s["header_main"] = f"{m['home']}  {score}  {m['away']}"
        s["header_sub"] = f"{m['competition'] or ''}  |  {dt}  |  {m['venue'] or ''}"
        s["header_meta"] = [("Customer", r["client"] or "-"), ("Competition", m["competition"] or "-"), ("Venue", m["venue"] or "-"), ("Date", dt)]
        rows = []
        for pid, st in res["players"].items():
            a = md["appearances"][pid]
            if a["appearance_status"] != "played":
                continue
            rows.append(dict(name=names[pid], team=m["home"] if a["team_id"] == m["home_team_id"] else m["away"], team_id=a["team_id"],
                             min=fmt(st["minutes"]), g=fmt(st["goals"]), a=fmt(st["assists"]), sh=fmt(st["shots"]), **{"pass": fmt(st["passes_attempted"])},
                             passpct=fmt(st["pass_completion"], 1, "%"), kp=fmt(st["key_passes"]), tkl=fmt(st["tackles"]), int=fmt(st["interceptions"])))
        rows.sort(key=lambda x: (x["team_id"] != m["home_team_id"], x["name"]))
        s["player_table"] = rows
        if r["report_type"] == "team":
            focus = r["team_id"]
            fname = m["home"] if focus == m["home_team_id"] else m["away"]
            png = charts.shot_map(md["events"], focus, "Shots")
            heat = charts.heatmap(md["events"], focus, fname)
            net = charts.passing_network(md["events"], focus, names, fname)
        else:
            png = charts.shot_map_pair(md["events"], m["home_team_id"], m["away_team_id"], m["home"], m["away"])
            heat = charts.heatmap_pair(md["events"], m["home_team_id"], m["away_team_id"], m["home"], m["away"])
            net = charts.network_pair(md["events"], m["home_team_id"], m["away_team_id"], m["home"], m["away"], names)
        if png:
            s["shot_map_b64"] = base64.b64encode(png).decode()
        if heat:
            s["heat_b64"] = base64.b64encode(heat).decode()
        if net:
            s["net_b64"] = base64.b64encode(net).decode()
    return s


def local_dt(v):
    from datetime import datetime
    try:
        return datetime.strptime(str(v)[:16].replace("T", " "), "%Y-%m-%d %H:%M").strftime("%d %B %Y, %H:%M")
    except ValueError:
        return str(v)


def _video_for(r, pid):
    """Only permitted, client-shareable footage is referenced in a report."""
    sql = ("SELECT c.start_seconds, c.event_category, c.notes, v.title FROM video_clips c JOIN video_assets v ON v.id=c.video_id "
           "WHERE c.player_id=? AND v.permission_status='permitted' AND v.access_restriction='client_shareable'")
    args = [pid]
    if r.get("match_id") if isinstance(r, dict) else r["match_id"]:
        sql += " AND (c.match_id=? OR v.match_id=?)"
        args += [r["match_id"], r["match_id"]]
    return [dict(title=x["title"], start=x["start_seconds"], category=x["event_category"], notes=x["notes"]) for x in q(sql, args)]


def _scouting_snapshot(r, s):
    sc = q("SELECT * FROM scouting_reports WHERE id=?", (r["scouting_id"],), one=True)
    p = q("SELECT p.*, t.name AS team FROM players p LEFT JOIN teams t ON t.id=p.current_team_id WHERE p.id=?", (sc["player_id"],), one=True)
    ms = q("SELECT m.match_code, m.kickoff, ht.name AS h, at.name AS a FROM scouting_report_matches x JOIN matches m ON m.id=x.match_id "
           "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id WHERE x.scouting_id=?", (sc["id"],))
    s.update(header_title="Scouting report", header_main=p["full_name"], header_sub=f"{sc['position_role'] or p['position'] or ''}  |  {p['team'] or ''}",
             header_meta=[("Client", r["client"] or "-"), ("Observed", sc["observation_date"] or "-"), ("Confidence", sc["confidence"]), ("Matches", str(len(ms)))],
             report_kind="Scouting report", data_status="validated")
    s["player"] = dict(name=p["full_name"], position=p["position"], team=p["team"], nationality=p["nationality"], verification=p["verification_status"], source=p["profile_source"])
    s["scouting"] = dict(position_role=sc["position_role"], date=sc["observation_date"], confidence=sc["confidence"], facts=sc["factual_evidence"],
                         technical=sc["technical_strengths"], tactical=sc["tactical_strengths"], development=sc["development_areas"],
                         decision=sc["decision_making"], recommendation=sc["recommendation"],
                         matches=[f"{x['match_code']}: {x['h']} v {x['a']} ({str(x['kickoff'])[:10]})" for x in ms])
    s["video_lines"] = [v["title"] + f" ({v['start']}s)" for v in _video_for({"match_id": None}, sc["player_id"])]
    return s


# ----------------------------------------------------------------------------- list / create
@bp.route("/")
def list_view():
    where, args = ["1=1"], []
    st = request.args.get("status", "")
    ty = request.args.get("type", "")
    if st:
        where.append("r.status=?")
        args.append(st)
    if ty:
        where.append("r.report_type=?")
        args.append(ty)
    rows = q("SELECT r.*, u.full_name AS author, c.name AS client, p.full_name AS player, m.match_code FROM reports r "
             "LEFT JOIN users u ON u.id=r.created_by LEFT JOIN clients c ON c.id=r.client_id LEFT JOIN players p ON p.id=r.player_id "
             f"LEFT JOIN matches m ON m.id=r.match_id WHERE {' AND '.join(where)} ORDER BY r.updated_at DESC", args)
    return render_template("reports/list.html", rows=rows, st=st, ty=ty, types=TYPES, can_create=has_perm("report.create"))


@bp.route("/new", methods=["GET", "POST"])
@perm_required("report.create")
def create():
    rtype = request.values.get("type", "player")
    if rtype not in TYPES:
        abort(400)
    if rtype == "scouting" and not has_perm("scouting.manage", "report.create"):
        abort(403)
    elig = "m.status IN ('data_validated','analysis_in_progress','report_under_review','approved','delivered_to_client','archived')"
    all_m = q(f"SELECT m.id, m.match_code, m.status, ht.name AS h, at.name AS a, m.home_team_id, m.away_team_id FROM matches m "
              "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
              "WHERE EXISTS (SELECT 1 FROM match_events e WHERE e.match_id=m.id) ORDER BY m.kickoff DESC")
    pairs = q("SELECT a.match_id, a.player_id, p.full_name, m.match_code FROM appearances a JOIN players p ON p.id=a.player_id "
              "JOIN matches m ON m.id=a.match_id WHERE a.appearance_status='played' ORDER BY m.kickoff DESC, p.full_name")
    scouts = q("SELECT s.id, p.full_name, s.observation_date, s.review_status FROM scouting_reports s JOIN players p ON p.id=s.player_id ORDER BY s.id DESC")
    clients = q("SELECT id, name FROM clients WHERE is_active=1 ORDER BY name")
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int) or None
        prov = bool(request.form.get("allow_provisional"))
        err, mid, pid, tid, sid, title = None, None, None, None, None, ""
        if rtype == "player":
            try:
                mid, pid = [int(x) for x in request.form.get("pair", ":").split(":")]
            except ValueError:
                err = "Choose a match and player."
        elif rtype in ("match", "team"):
            mid = request.form.get("match_id", type=int)
            if rtype == "team":
                tid = request.form.get("team_id", type=int)
        else:
            sid = request.form.get("scouting_id", type=int)
            if not sid or not scalar("SELECT COUNT(*) FROM scouting_reports WHERE id=?", (sid,)):
                err = "Choose a scouting record."
        m = q("SELECT m.*, ht.name AS h, at.name AS a FROM matches m JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id WHERE m.id=?", (mid,), one=True) if mid else None
        if rtype != "scouting":
            if not m:
                err = err or "Choose a match."
            elif rtype == "team" and tid not in (m["home_team_id"], m["away_team_id"]):
                err = "Choose which team the report is for."
            elif m["status"] not in C.VALIDATED_OR_LATER and not prov:
                err = "This match's data has not been validated. Tick 'allow provisional data' to continue - the report will be marked PROVISIONAL."
        if err:
            flash(err, "error")
        else:
            if rtype == "player":
                pn = scalar("SELECT full_name FROM players WHERE id=?", (pid,), "")
                title = f"{pn} - {m['h']} v {m['a']}"
            elif rtype == "match":
                title = f"Match analysis - {m['h']} v {m['a']}"
            elif rtype == "team":
                title = f"Team report - {m['h'] if tid == m['home_team_id'] else m['a']} ({m['h']} v {m['a']})"
            else:
                title = "Scouting report - " + scalar("SELECT p.full_name FROM scouting_reports s JOIN players p ON p.id=s.player_id WHERE s.id=?", (sid,), "")
            valid = m and m["status"] in C.VALIDATED_OR_LATER
            rid = ex("INSERT INTO reports (report_type, title, match_id, player_id, team_id, scouting_id, client_id, status, data_status, content, created_by) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (rtype, title, mid, pid, tid, sid, client_id, "draft", "validated" if (valid or rtype == "scouting") else "provisional",
                                                       json.dumps({"input": {}}), g.user["id"]))
            audit("report.create", "reports", rid, {"type": rtype, "title": title})
            flash("Report draft created. Add your analysis below.", "ok")
            return redirect(url_for("reports.detail", rid=rid))
    return render_template("reports/new.html", rtype=rtype, types=TYPES, matches=all_m, pairs=pairs, scouts=scouts, clients=clients)


# ----------------------------------------------------------------------------- detail / edit
@bp.route("/<int:rid>")
def detail(rid):
    r = _report(rid)
    content = _content(r)
    versions = q("SELECT v.*, u.full_name FROM report_versions v LEFT JOIN users u ON u.id=v.created_by WHERE v.report_id=? ORDER BY v.version DESC", (rid,))
    shares = q("SELECT s.*, c.name AS client, u.full_name AS by FROM report_shares s JOIN clients c ON c.id=s.client_id LEFT JOIN users u ON u.id=s.shared_by "
               "WHERE s.report_id=? ORDER BY s.id DESC", (rid,))
    editable = has_perm("report.create") and _is_owner(r) and r["status"] in ("draft", "returned", "withdrawn")
    clients = q("SELECT id, name FROM clients WHERE is_active=1 ORDER BY name")
    return render_template("reports/detail.html", r=r, inp=content.get("input", {}), versions=versions, shares=shares, editable=editable,
                           lists=[(k, LIST_LABELS[k]) for k in INPUT_LISTS[r["report_type"]]], clients=clients,
                           rubric=get_setting("rating_rubric"), types=TYPES,
                           can_approve=has_perm("report.approve") and r["status"] == "under_review" and not _is_owner(r),
                           can_share=has_perm("report.share") and r["status"] in ("approved", "delivered"),
                           can_withdraw=has_perm("report.share", "report.approve") and r["status"] in ("approved", "delivered"),
                           own=_is_owner(r))


@bp.route("/<int:rid>/save", methods=["POST"])
@perm_required("report.create")
def save(rid):
    r = _report(rid)
    if not (_is_owner(r) and r["status"] in ("draft", "returned", "withdrawn")):
        abort(403)
    inp = {k: _lines(request.form.get(k)) for k in INPUT_LISTS[r["report_type"]]}
    if r["report_type"] == "player":
        raw = request.form.get("rating", "").strip()
        if raw:
            try:
                val = float(raw)
                if not 0 <= val <= 10:
                    raise ValueError
            except ValueError:
                flash("Rating must be a number from 0 to 10.", "error")
                return redirect(url_for("reports.detail", rid=rid))
            just = request.form.get("rating_justification", "").strip()
            if not just:
                flash("A rating needs a justification that follows the rating rubric.", "error")
                return redirect(url_for("reports.detail", rid=rid))
            inp["rating"], inp["rating_justification"] = round(val, 1), just[:600]
    cid = request.form.get("client_id", type=int) or None
    ex("UPDATE reports SET content=?, client_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps({"input": inp}), cid, rid))
    audit("report.save", "reports", rid)
    flash("Draft saved.", "ok")
    return redirect(url_for("reports.detail", rid=rid))


def _pdf_response(data, name, inline=True):
    from io import BytesIO
    return send_file(BytesIO(data), mimetype="application/pdf", download_name=name, as_attachment=not inline)


@bp.route("/<int:rid>/preview.pdf")
def preview(rid):
    r = _report(rid)
    try:
        snap = build_snapshot(r)
        data = pdfgen.render(snap, watermark="DRAFT")
    except ValueError as e:
        abort(400, str(e))
    return _pdf_response(data, f"report_{rid}_preview.pdf")


@bp.route("/<int:rid>/v/<int:ver>.pdf")
def version_pdf(rid, ver):
    r = _report(rid)
    v = q("SELECT * FROM report_versions WHERE report_id=? AND version=?", (rid, ver), one=True)
    if not v or not v["pdf_path"]:
        abort(404)
    path = Path(current_app.config["REPORT_DIR"]) / v["pdf_path"]
    if not path.exists():
        abort(404)
    wm = "WITHDRAWN" if r["status"] == "withdrawn" else None
    if wm:
        data = pdfgen.render(json.loads(v["content"]), watermark=wm)
        return _pdf_response(data, f"report_{rid}_v{ver}.pdf")
    audit("report.download", "reports", rid, {"version": ver})
    return send_file(path, mimetype="application/pdf", download_name=f"report_{rid}_v{ver}.pdf")


@bp.route("/<int:rid>/submit", methods=["POST"])
@perm_required("report.create")
def submit(rid):
    r = _report(rid)
    if not (_is_owner(r) and r["status"] in ("draft", "returned", "withdrawn")):
        abort(403)
    if r["report_type"] != "scouting" and r["data_status"] == "validated" and r["match_status"] not in C.VALIDATED_OR_LATER:
        flash("The match data is no longer validated.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    if r["report_type"] == "scouting" and scalar("SELECT review_status FROM scouting_reports WHERE id=?", (r["scouting_id"],), "") == "draft":
        flash("Submit the scouting record for review first.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    ver = r["current_version"] + 1
    try:
        snap = build_snapshot(r, version=ver)
        run_id = None
        if r["report_type"] != "scouting":
            res = analyse_match(r["match_id"], provisional=r["data_status"] == "provisional")
            run_id = store_run(ex, r["match_id"], g.user["id"], res, f"Report #{rid} v{ver}")
        data = pdfgen.render(snap)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("reports.detail", rid=rid))
    fname = f"report_{rid}_v{ver}.pdf"
    (Path(current_app.config["REPORT_DIR"]) / fname).write_bytes(data)
    ex("INSERT INTO report_versions (report_id, version, content, pdf_path, analysis_run_id, created_by, note) VALUES (?,?,?,?,?,?,?)",
       (rid, ver, json.dumps(snap), fname, run_id, g.user["id"], request.form.get("note", "")[:200] or ("Resubmitted after changes" if ver > 1 else "First submission")))
    ex("UPDATE reports SET status='under_review', current_version=?, review_note=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (ver, rid))
    if r["match_id"] and r["match_status"] in ("data_validated", "analysis_in_progress"):
        set_status(r["match_id"], "report_under_review", g.user["id"], f"Report #{rid} submitted")
    audit("report.submit", "reports", rid, {"version": ver})
    flash(f"Version {ver} generated and submitted for review.", "ok")
    return redirect(url_for("reports.detail", rid=rid))


@bp.route("/<int:rid>/approve", methods=["POST"])
@perm_required("report.approve")
def approve(rid):
    r = _report(rid)
    if r["status"] != "under_review":
        abort(400, "Only reports under review can be approved.")
    if _is_owner(r):
        flash("You cannot approve your own report.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    ex("UPDATE reports SET status='approved', reviewer_id=?, approved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (g.user["id"], rid))
    if r["match_id"] and r["match_status"] == "report_under_review":
        set_status(r["match_id"], "approved", g.user["id"], f"Report #{rid} approved")
    audit("report.approve", "reports", rid, {"version": r["current_version"]})
    flash("Report approved. It can now be shared with the client.", "ok")
    return redirect(url_for("reports.detail", rid=rid))


@bp.route("/<int:rid>/return", methods=["POST"])
@perm_required("report.approve")
def send_back(rid):
    r = _report(rid)
    note = request.form.get("note", "").strip()
    if r["status"] != "under_review":
        abort(400)
    if not note:
        flash("Explain what needs to change.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    ex("UPDATE reports SET status='returned', review_note=?, reviewer_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (note[:1000], g.user["id"], rid))
    audit("report.return", "reports", rid, {"note": note})
    flash("Report returned to the analyst.", "ok")
    return redirect(url_for("reports.list_view"))


@bp.route("/<int:rid>/share", methods=["POST"])
@perm_required("report.share")
def share(rid):
    r = _report(rid)
    if r["status"] not in ("approved", "delivered"):
        abort(400, "Only approved reports can be shared.")
    cid = request.form.get("client_id", type=int) or r["client_id"]
    if not cid or not scalar("SELECT COUNT(*) FROM clients WHERE id=? AND is_active=1", (cid,)):
        flash("Choose the client who should receive this report.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    if scalar("SELECT COUNT(*) FROM report_shares WHERE report_id=? AND client_id=? AND version=? AND status='delivered'", (rid, cid, r["current_version"])):
        flash("This version has already been shared with that client.", "info")
        return redirect(url_for("reports.detail", rid=rid))
    ex("INSERT INTO report_shares (report_id, client_id, version, shared_by) VALUES (?,?,?,?)", (rid, cid, r["current_version"], g.user["id"]))
    ex("UPDATE reports SET status='delivered', client_id=?, delivered_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid, rid))
    if r["match_id"] and r["match_status"] == "approved":
        set_status(r["match_id"], "delivered_to_client", g.user["id"], f"Report #{rid} delivered")
    audit("report.share", "reports", rid, {"client": cid, "version": r["current_version"]})
    flash("Report shared. The client can now see it in their portal.", "ok")
    return redirect(url_for("reports.detail", rid=rid))


@bp.route("/<int:rid>/withdraw", methods=["POST"])
def withdraw(rid):
    r = _report(rid)
    if not has_perm("report.share", "report.approve"):
        abort(403)
    reason = request.form.get("reason", "").strip()
    if r["status"] not in ("approved", "delivered") or not reason:
        flash("Give a reason to withdraw a report.", "error")
        return redirect(url_for("reports.detail", rid=rid))
    ex("UPDATE reports SET status='withdrawn', review_note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (reason[:1000], rid))
    ex("UPDATE report_shares SET status='revoked' WHERE report_id=?", (rid,))
    audit("report.withdraw", "reports", rid, {"reason": reason})
    flash("Report withdrawn. Clients can no longer open it. The analyst can correct and reissue it.", "ok")
    return redirect(url_for("reports.detail", rid=rid))
