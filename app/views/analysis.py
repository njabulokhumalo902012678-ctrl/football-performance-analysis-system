"""Analysis screens: match/team/player statistics, data-quality, analyst notes, metric definitions and self-test."""
from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import charts, constants as C
from ..db import ex, q, scalar
from ..metrics import METRICS, NAMES, analyse_match, fmt, load_match, player_career, run_selftests, store_run
from ..security import audit, has_perm, perm_required
from ..workflow import set_status
from .matches import match_row

bp = Blueprint("analysis", __name__, url_prefix="/analysis")

PLAYER_TABLE = [("minutes", "Min"), ("goals", "G"), ("assists", "A"), ("shots", "Sh"), ("shots_on_target", "SoT"),
                ("passes_attempted", "Pass"), ("pass_completion", "Pass %"), ("key_passes", "KP"), ("tackles", "Tkl"),
                ("interceptions", "Int"), ("clearances", "Clr"), ("yellow_cards", "YC"), ("red_cards", "RC")]
TEAM_TABLE = [("goals_for", "Goals"), ("shots", "Shots"), ("shots_on_target", "Shots on target"), ("shot_accuracy", "Shot accuracy %"),
              ("corners", "Corners"), ("fouls", "Fouls"), ("yellow_cards", "Yellow cards"), ("red_cards", "Red cards"),
              ("passes_attempted", "Passes attempted"), ("passes_completed", "Passes completed"), ("pass_completion", "Pass completion %"),
              ("key_passes", "Key passes"), ("crosses", "Crosses"), ("tackles", "Tackles"), ("interceptions", "Interceptions"),
              ("clearances", "Clearances"), ("blocks", "Blocks"), ("recoveries", "Recoveries"), ("possession", "Possession %")]


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client" or not has_perm("analysis.view"):
        abort(403)


def _fmtfn(code):
    return (lambda v: fmt(v, 1, "%")) if code in ("shot_accuracy", "pass_completion", "possession") else (lambda v: fmt(v))


@bp.route("/")
def index():
    rows = q("SELECT m.id, m.match_code, m.kickoff, m.status, m.home_score, m.away_score, ht.name AS home, at.name AS away, "
             "(SELECT COUNT(*) FROM analysis_runs r WHERE r.match_id=m.id) AS runs FROM matches m "
             "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
             "WHERE m.status IN ('data_validated','analysis_in_progress','report_under_review','approved','delivered_to_client','archived') "
             "OR EXISTS (SELECT 1 FROM match_events e WHERE e.match_id=m.id) ORDER BY m.kickoff DESC")
    return render_template("analysis/index.html", rows=rows)


@bp.route("/match/<int:mid>")
def match_view(mid):
    m = match_row(mid)
    prov = request.args.get("provisional") == "1"
    valid = m["status"] in C.VALIDATED_OR_LATER
    if not valid and not prov:
        return render_template("analysis/not_validated.html", m=m)
    res = analyse_match(mid, provisional=prov and not valid)
    md = res["match_data"]
    names = {r["id"]: r["full_name"] for r in q("SELECT id, full_name FROM players")}
    team_rows = []
    for code, label in TEAM_TABLE:
        f = _fmtfn(code)
        team_rows.append((label, f(res["teams"][m["home_team_id"]][code]), f(res["teams"][m["away_team_id"]][code]),
                          res["teams"][m["home_team_id"]][code]["note"] if res["teams"][m["home_team_id"]][code]["status"] != "ok" else ""))
    players = []
    for pid, st in res["players"].items():
        a = md["appearances"][pid]
        players.append(dict(id=pid, name=names[pid], team=m["home"] if a["team_id"] == m["home_team_id"] else m["away"],
                            team_id=a["team_id"], role=a["role"],
                            cells=[_fmtfn(c)(st[c]) for c, _ in PLAYER_TABLE], status=a["appearance_status"]))
    players.sort(key=lambda p: (p["team_id"] != m["home_team_id"], p["role"] != "starter", p["name"]))
    notes = q("SELECT n.*, u.full_name AS author, p.full_name AS player FROM analyst_notes n LEFT JOIN users u ON u.id=n.author_id "
              "LEFT JOIN players p ON p.id=n.player_id WHERE n.match_id=? ORDER BY n.id DESC", (mid,))
    runs = q("SELECT r.*, u.full_name FROM analysis_runs r LEFT JOIN users u ON u.id=r.run_by WHERE r.match_id=? ORDER BY r.id DESC LIMIT 5", (mid,))
    timeline = [e for e in md["events"] if e["code"] in ("goal", "penalty", "own_goal", "card", "substitution")]
    pl_lookup = names
    ev = md["events"]
    pnames = {pid: n for pid, n in names.items()}
    adv = {}
    for key, tid in (("home", m["home_team_id"]), ("away", m["away_team_id"])):
        adv[key] = dict(heat=len(charts.heat_points(ev, tid)) >= charts.HEAT_MIN_POINTS, net=charts.network_data(ev, tid, pnames) is not None)
    for pl in players:
        pl["heat"] = len(charts.heat_points(ev, pl["team_id"], pl["id"])) >= 8
    return render_template("analysis/match.html", adv=adv, m=m, res=res, team_rows=team_rows, players=players, headers=[h for _, h in PLAYER_TABLE],
                           notes=notes, runs=runs, timeline=timeline, names=pl_lookup, prov=prov and not valid, valid=valid,
                           can_run=has_perm("analysis.run"), can_note=has_perm("notes.edit"),
                           has_coords=any(e["x_start"] is not None for e in md["events"] if e["code"] in ("shot", "goal", "penalty")),
                           teams={m["home_team_id"]: m["home"], m["away_team_id"]: m["away"]})


@bp.route("/match/<int:mid>/run", methods=["POST"])
@perm_required("analysis.run")
def run(mid):
    m = match_row(mid)
    if m["status"] not in C.VALIDATED_OR_LATER:
        flash("Analysis runs are only stored for validated data.", "error")
        return redirect(url_for("analysis.match_view", mid=mid))
    res = analyse_match(mid)
    rid = store_run(ex, mid, g.user["id"], res, request.form.get("note", "")[:200])
    if m["status"] == "data_validated":
        set_status(mid, "analysis_in_progress", g.user["id"], "Analysis started")
    audit("analysis.run", "matches", mid, {"run": rid})
    flash(f"Analysis run #{rid} stored.", "ok")
    return redirect(url_for("analysis.match_view", mid=mid))


@bp.route("/match/<int:mid>/note", methods=["POST"])
@perm_required("notes.edit")
def add_note(mid):
    match_row(mid)
    body = request.form.get("body", "").strip()
    ntype = request.form.get("note_type", "observation")
    pid = request.form.get("player_id", type=int)
    if ntype not in ("observation", "tactical", "strength", "development", "training", "recommendation", "fact"):
        abort(400)
    if not body:
        flash("Write the note first.", "error")
    else:
        if pid and not scalar("SELECT COUNT(*) FROM appearances WHERE match_id=? AND player_id=?", (mid, pid)):
            pid = None
        ex("INSERT INTO analyst_notes (match_id, player_id, author_id, note_type, body, is_fact) VALUES (?,?,?,?,?,?)",
           (mid, pid, g.user["id"], ntype, body[:3000], 1 if ntype == "fact" else 0))
        audit("analysis.note", "matches", mid, {"type": ntype})
        flash("Note saved. Notes are marked as analyst opinion unless recorded as fact.", "ok")
    return redirect(url_for("analysis.match_view", mid=mid) + "#notes")


@bp.route("/match/<int:mid>/chart/<kind>.png")
def chart(mid, kind):
    m = match_row(mid)
    prov = request.args.get("provisional") == "1"
    if m["status"] not in C.VALIDATED_OR_LATER and not prov:
        abort(404)
    res = analyse_match(mid, provisional=prov)
    md = res["match_data"]
    ht, at = m["home_team_id"], m["away_team_id"]
    if kind == "teams":
        rows = []
        for code, label in (("shots", "Shots"), ("shots_on_target", "Shots on target"), ("corners", "Corners"), ("fouls", "Fouls"),
                            ("passes_attempted", "Passes"), ("tackles", "Tackles"), ("interceptions", "Interceptions")):
            h, a = res["teams"][ht][code], res["teams"][at][code]
            if h["status"] == "ok" and a["status"] == "ok":
                rows.append((label, h["value"], a["value"]))
        png = charts.team_comparison(rows, m["home"], m["away"])
    elif kind in ("shots_home", "shots_away"):
        tid = ht if kind == "shots_home" else at
        png = charts.shot_map(md["events"], tid, f"{m['home'] if tid == ht else m['away']} shots")
    elif kind in ("heat_home", "heat_away"):
        tid = ht if kind == "heat_home" else at
        png = charts.heatmap(md["events"], tid, m["home"] if tid == ht else m["away"])
    elif kind in ("net_home", "net_away"):
        tid = ht if kind == "net_home" else at
        nm = {r["id"]: r["full_name"] for r in q("SELECT id, full_name FROM players")}
        png = charts.passing_network(md["events"], tid, nm, m["home"] if tid == ht else m["away"])
    elif kind == "heat_player":
        pid = request.args.get("pid", type=int)
        app_ = md["appearances"].get(pid)
        if not app_:
            abort(404)
        nm = scalar("SELECT full_name FROM players WHERE id=?", (pid,), "Player")
        png = charts.heatmap(md["events"], app_["team_id"], nm, player_id=pid)
    else:
        abort(404)
    if png is None:
        abort(404)                       # not enough collected data: no chart rather than an invented one
    return Response(png, mimetype="image/png")


@bp.route("/player/<int:pid>")
def player(pid):
    p = q("SELECT p.*, t.name AS team FROM players p LEFT JOIN teams t ON t.id=p.current_team_id WHERE p.id=?", (pid,), one=True)
    if not p:
        abort(404)
    prov = request.args.get("provisional") == "1"
    sql = ("SELECT m.id, m.match_code, m.kickoff, ht.name AS home, at.name AS away, m.status FROM appearances a JOIN matches m ON m.id=a.match_id "
           "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id WHERE a.player_id=? ")
    if not prov:
        sql += "AND m.status IN ('data_validated','analysis_in_progress','report_under_review','approved','delivered_to_client','archived') "
    ms = q(sql + "ORDER BY m.kickoff", (pid,))
    picked = request.args.getlist("m", type=int)
    use = [m for m in ms if (not picked or m["id"] in picked)]
    per_match, scopes = [], []
    for m in use:
        md = load_match(m["id"], prov)
        st = player_career(pid, [m["id"]], prov)
        per_match.append((m, st))
        scopes.append(frozenset(md["scope"]))
    agg = player_career(pid, [m["id"] for m in use], prov) if use else None
    consistent = len(set(scopes)) <= 1
    codes = [("appearances", "Appearances"), ("minutes", "Minutes")] + [(c, NAMES[c]) for c in
             ("goals", "assists", "shots", "shots_on_target", "shot_accuracy", "passes_attempted", "passes_completed", "pass_completion",
              "key_passes", "crosses", "tackles", "interceptions", "clearances", "blocks", "recoveries", "duels", "aerial_duels",
              "fouls", "yellow_cards", "red_cards", "set_pieces_taken", "goals_per90", "assists_per90", "shots_per90", "tackles_per90")]
    rows = []
    for code, label in codes:
        f = _fmtfn(code) if code in ("shot_accuracy", "pass_completion") else (lambda v: fmt(v, 2))
        rows.append(dict(label=label, cells=[f(st[code]) for _, st in per_match], total=f(agg[code]) if agg else "-",
                         note=agg[code]["note"] if agg and agg[code]["status"] != "ok" else ""))
    trend_ok = consistent and len(use) >= 2
    return render_template("analysis/player.html", p=p, ms=ms, use=use, picked=picked, rows=rows, consistent=consistent, prov=prov, trend_ok=trend_ok)


@bp.route("/player/<int:pid>/trend/<code>.png")
def player_trend(pid, code):
    if code not in NAMES:
        abort(404)
    prov = request.args.get("provisional") == "1"
    ms = q("SELECT m.id, m.match_code FROM appearances a JOIN matches m ON m.id=a.match_id WHERE a.player_id=? ORDER BY m.kickoff", (pid,))
    labels, vals, scopes = [], [], set()
    for m in ms:
        md = load_match(m["id"], prov)
        if not prov and m["id"] and md["match"]["status"] not in C.VALIDATED_OR_LATER:
            continue
        st = player_career(pid, [m["id"]], prov)[code]
        scopes.add(frozenset(md["scope"]))
        labels.append(m["match_code"])
        vals.append(st["value"] if st["status"] in ("ok", "partial") else None)
    if len(scopes) > 1:
        abort(404)
    png = charts.trend(labels, vals, NAMES[code])
    if not png:
        abort(404)
    return Response(png, mimetype="image/png")


@bp.route("/metrics")
def metrics():
    defs = q("SELECT * FROM metric_definitions ORDER BY subject_scope, code")
    results = run_selftests()
    return render_template("analysis/metrics.html", defs=defs, results=results, passed=sum(1 for r in results if r[1]), total=len(results))
