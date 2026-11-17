"""Video analysis (permission-controlled) and scouting records."""
import secrets
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from .. import constants as C
from ..db import ex, q, scalar
from ..forms import F, parse_form
from ..security import audit, has_perm, perm_required

bp = Blueprint("scouting", __name__)
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client" or not has_perm("video.view", "scouting.view", "video.manage", "scouting.manage"):
        abort(403)


# ----------------------------------------------------------------------------- video
@bp.route("/video/")
@perm_required("video.view")
def videos():
    rows = q("SELECT v.*, m.match_code, (SELECT COUNT(*) FROM video_clips c WHERE c.video_id=v.id) AS clips FROM video_assets v "
             "LEFT JOIN matches m ON m.id=v.match_id ORDER BY v.id DESC")
    return render_template("scouting/videos.html", rows=rows, can_manage=has_perm("video.manage"))


@bp.route("/video/new", methods=["GET", "POST"])
@perm_required("video.manage")
def video_new():
    fields = [F("title", "Title", req=True), F("match_id", "Match", "fk", fk=("matches", "match_code")),
              F("reference", "Video link or reference", help="Approved link (e.g. company drive) - or upload a file below."),
              F("permission_status", "Permission status", "select", options=C.VIDEO_PERMISSIONS, req=True, default="pending"),
              F("access_restriction", "Access restriction", "select", options=["internal_only", "client_shareable"], req=True, default="internal_only"),
              F("licence_notes", "Source, licence or permission notes", "textarea", req=True)]
    if request.method == "POST":
        vals, errs = parse_form(fields, request.form)
        up = request.files.get("file")
        if not vals.get("reference") and not (up and up.filename):
            errs["reference"] = "Provide a reference link or upload a file."
        if vals.get("access_restriction") == "client_shareable" and vals.get("permission_status") != "permitted":
            errs["access_restriction"] = "Footage can only be client-shareable when permission status is 'permitted'."
        path = None
        if up and up.filename:
            ext = Path(up.filename).suffix.lower()
            if ext not in VIDEO_EXT:
                errs["reference"] = "Unsupported video type. Use mp4, mov, webm, mkv or m4v."
            elif not errs:
                path = secrets.token_hex(12) + ext
                up.save(Path(current_app.config["VIDEO_DIR"]) / path)
        if errs:
            flash("Some details need attention.", "error")
            return render_template("scouting/video_form.html", fields=fields, form=request.form, errs=errs), 422
        vid = ex("INSERT INTO video_assets (title, match_id, reference, file_path, permission_status, licence_notes, access_restriction, uploaded_by) "
                 "VALUES (?,?,?,?,?,?,?,?)", (vals["title"], vals["match_id"], vals["reference"], path, vals["permission_status"],
                                              vals["licence_notes"], vals["access_restriction"], g.user["id"]))
        audit("video.create", "video_assets", vid, {"permission": vals["permission_status"], "restriction": vals["access_restriction"]})
        flash("Video registered.", "ok")
        return redirect(url_for("scouting.video_detail", vid=vid))
    return render_template("scouting/video_form.html", fields=fields, form=None, errs={})


@bp.route("/video/<int:vid>")
@perm_required("video.view")
def video_detail(vid):
    v = q("SELECT v.*, m.match_code FROM video_assets v LEFT JOIN matches m ON m.id=v.match_id WHERE v.id=?", (vid,), one=True)
    if not v:
        abort(404)
    clips = q("SELECT c.*, p.full_name AS player, u.full_name AS author FROM video_clips c LEFT JOIN players p ON p.id=c.player_id "
              "LEFT JOIN users u ON u.id=c.created_by WHERE c.video_id=? ORDER BY c.start_seconds", (vid,))
    players = q("SELECT id, full_name FROM players ORDER BY full_name")
    return render_template("scouting/video_detail.html", v=v, clips=clips, players=players, categories=C.VIDEO_CATEGORIES,
                           can_manage=has_perm("video.manage"), playable=bool(v["file_path"]) and v["permission_status"] in ("permitted", "restricted", "pending"))


@bp.route("/video/<int:vid>/permission", methods=["POST"])
@perm_required("video.manage")
def video_permission(vid):
    v = q("SELECT * FROM video_assets WHERE id=?", (vid,), one=True)
    if not v:
        abort(404)
    perm = request.form.get("permission_status")
    restr = request.form.get("access_restriction")
    if perm not in C.VIDEO_PERMISSIONS or restr not in ("internal_only", "client_shareable"):
        abort(400)
    if restr == "client_shareable" and perm != "permitted":
        flash("Footage can only be client-shareable when permission status is 'permitted'.", "error")
    else:
        ex("UPDATE video_assets SET permission_status=?, access_restriction=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (perm, restr, vid))
        audit("video.permission", "video_assets", vid, {"from": [v["permission_status"], v["access_restriction"]], "to": [perm, restr]})
        flash("Permission updated.", "ok")
    return redirect(url_for("scouting.video_detail", vid=vid))


@bp.route("/video/<int:vid>/file")
@perm_required("video.view")
def video_file(vid):
    v = q("SELECT * FROM video_assets WHERE id=?", (vid,), one=True)
    if not v or not v["file_path"] or v["permission_status"] == "not_permitted":
        abort(404)
    path = Path(current_app.config["VIDEO_DIR"]) / v["file_path"]
    if not path.exists():
        abort(404)
    audit("video.view_file", "video_assets", vid)
    return send_file(path, conditional=True)


@bp.route("/video/<int:vid>/clip", methods=["POST"])
@perm_required("video.manage")
def clip_add(vid):
    v = q("SELECT * FROM video_assets WHERE id=?", (vid,), one=True)
    if not v:
        abort(404)
    if v["permission_status"] == "not_permitted":
        flash("Clips cannot be created from footage that is not permitted.", "error")
        return redirect(url_for("scouting.video_detail", vid=vid))
    fields = [F("player_id", "Player", "fk", fk=("players", "full_name")), F("start_seconds", "Start (seconds)", "int", req=True),
              F("end_seconds", "End (seconds)", "int"), F("event_category", "Event", "select", options=C.VIDEO_CATEGORIES),
              F("tags", "Tags"), F("notes", "Analyst notes", "textarea")]
    vals, errs = parse_form(fields, request.form)
    if not errs and vals["start_seconds"] < 0:
        errs["start_seconds"] = "Start cannot be negative."
    if not errs and vals.get("end_seconds") is not None and vals["end_seconds"] <= vals["start_seconds"]:
        errs["end_seconds"] = "End must be after the start."
    if errs:
        flash(" ".join(errs.values()), "error")
    else:
        cid = ex("INSERT INTO video_clips (video_id, match_id, player_id, start_seconds, end_seconds, event_category, tags, notes, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                 (vid, v["match_id"], vals["player_id"], vals["start_seconds"], vals["end_seconds"], vals["event_category"], vals["tags"], vals["notes"], g.user["id"]))
        audit("video.clip", "video_clips", cid)
        flash("Clip tagged.", "ok")
    return redirect(url_for("scouting.video_detail", vid=vid))


@bp.route("/video/clip/<int:cid>/delete", methods=["POST"])
@perm_required("video.manage")
def clip_delete(cid):
    c = q("SELECT * FROM video_clips WHERE id=?", (cid,), one=True)
    if not c:
        abort(404)
    ex("DELETE FROM video_clips WHERE id=?", (cid,))
    audit("video.clip_delete", "video_clips", cid)
    return redirect(url_for("scouting.video_detail", vid=c["video_id"]))


# ----------------------------------------------------------------------------- scouting
SC_FIELDS = [
    F("player_id", "Player", "fk", fk=("players", "full_name"), req=True),
    F("position_role", "Position or role observed"), F("observation_date", "Date of observation", "date"),
    F("factual_evidence", "Factual evidence (recorded facts only)", "textarea", rows=4, help="Things that can be checked: minutes, events, video timestamps."),
    F("technical_strengths", "Technical strengths (opinion)", "textarea"), F("tactical_strengths", "Tactical strengths (opinion)", "textarea"),
    F("development_areas", "Development areas (opinion)", "textarea"), F("decision_making", "Decision-making observations (opinion)", "textarea"),
    F("video_refs", "Video references", "textarea", help="Clip titles and timestamps that support the assessment."),
    F("confidence", "Confidence level", "select", options=C.CONFIDENCE_LEVELS, req=True, default="low"),
    F("recommendation", "Recommendation (opinion)", "textarea"),
]


@bp.route("/scouting/")
@perm_required("scouting.view")
def scouting_list():
    rows = q("SELECT s.*, p.full_name AS player, u.full_name AS analyst, (SELECT COUNT(*) FROM scouting_report_matches x WHERE x.scouting_id=s.id) AS sample "
             "FROM scouting_reports s JOIN players p ON p.id=s.player_id LEFT JOIN users u ON u.id=s.analyst_id ORDER BY s.updated_at DESC")
    return render_template("scouting/list.html", rows=rows, can_manage=has_perm("scouting.manage"))


def _scout_form(s=None):
    selected = {r["match_id"] for r in q("SELECT match_id FROM scouting_report_matches WHERE scouting_id=?", (s["id"],))} if s else set()
    all_matches = q("SELECT m.id, m.match_code, ht.name AS h, at.name AS a, m.kickoff FROM matches m JOIN teams ht ON ht.id=m.home_team_id "
                    "JOIN teams at ON at.id=m.away_team_id ORDER BY m.kickoff DESC")
    if request.method == "POST":
        vals, errs = parse_form(SC_FIELDS, request.form)
        chosen = {int(x) for x in request.form.getlist("matches") if x.isdigit()}
        chosen = {m for m in chosen if scalar("SELECT COUNT(*) FROM matches WHERE id=?", (m,))}
        if vals.get("confidence") == "high" and len(chosen) < 3:
            errs["confidence"] = "High confidence needs at least 3 observed matches (sample size)."
        if not vals.get("factual_evidence") and not errs:
            errs["factual_evidence"] = "Record at least some factual evidence to support the assessment."
        if errs:
            flash("Some details need attention.", "error")
            return render_template("scouting/form.html", s=s, fields=SC_FIELDS, form=request.form, errs=errs, matches=all_matches, selected=chosen), 422
        names = list(vals)
        if s:
            ex("UPDATE scouting_reports SET " + ", ".join(f"{n}=?" for n in names) + ", updated_at=CURRENT_TIMESTAMP WHERE id=?", [vals[n] for n in names] + [s["id"]])
            sid = s["id"]
            audit("scouting.update", "scouting_reports", sid)
        else:
            sid = ex(f"INSERT INTO scouting_reports ({', '.join(names)}, analyst_id) VALUES ({', '.join('?' * len(names))}, ?)", [vals[n] for n in names] + [g.user["id"]])
            audit("scouting.create", "scouting_reports", sid)
        ex("DELETE FROM scouting_report_matches WHERE scouting_id=?", (sid,))
        for mid in chosen:
            ex("INSERT INTO scouting_report_matches (scouting_id, match_id) VALUES (?,?)", (sid, mid))
        flash("Scouting record saved.", "ok")
        return redirect(url_for("scouting.scouting_detail", sid=sid))
    return render_template("scouting/form.html", s=s, fields=SC_FIELDS, form=None, errs={}, matches=all_matches, selected=selected)


@bp.route("/scouting/new", methods=["GET", "POST"])
@perm_required("scouting.manage")
def scouting_new():
    return _scout_form(None)


@bp.route("/scouting/<int:sid>/edit", methods=["GET", "POST"])
@perm_required("scouting.manage")
def scouting_edit(sid):
    s = q("SELECT * FROM scouting_reports WHERE id=?", (sid,), one=True)
    if not s:
        abort(404)
    if s["review_status"] == "approved":
        flash("Approved scouting records are locked. Create a new record to update the assessment.", "error")
        return redirect(url_for("scouting.scouting_detail", sid=sid))
    return _scout_form(s)


@bp.route("/scouting/<int:sid>")
@perm_required("scouting.view")
def scouting_detail(sid):
    s = q("SELECT s.*, p.full_name AS player, u.full_name AS analyst FROM scouting_reports s JOIN players p ON p.id=s.player_id "
          "LEFT JOIN users u ON u.id=s.analyst_id WHERE s.id=?", (sid,), one=True)
    if not s:
        abort(404)
    ms = q("SELECT m.id, m.match_code, m.kickoff, ht.name AS h, at.name AS a FROM scouting_report_matches x JOIN matches m ON m.id=x.match_id "
           "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id WHERE x.scouting_id=?", (sid,))
    return render_template("scouting/detail.html", s=s, ms=ms, can_manage=has_perm("scouting.manage"), can_review=has_perm("report.approve"))


@bp.route("/scouting/<int:sid>/status", methods=["POST"])
def scouting_status(sid):
    s = q("SELECT * FROM scouting_reports WHERE id=?", (sid,), one=True)
    if not s:
        abort(404)
    new = request.form.get("status")
    if new == "submitted" and has_perm("scouting.manage") and s["review_status"] in ("draft", "returned"):
        pass
    elif new in ("approved", "returned") and has_perm("report.approve") and s["review_status"] == "submitted":
        pass
    else:
        abort(403)
    ex("UPDATE scouting_reports SET review_status=?, reviewer_id=CASE WHEN ? IN ('approved','returned') THEN ? ELSE reviewer_id END, updated_at=CURRENT_TIMESTAMP WHERE id=?",
       (new, new, g.user["id"], sid))
    audit("scouting.status", "scouting_reports", sid, {"to": new})
    flash(f"Scouting record {new}.", "ok")
    return redirect(url_for("scouting.scouting_detail", sid=sid))
