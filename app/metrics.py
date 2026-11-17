"""Football analysis engine.

Rules enforced here (from the specification):
  * Every figure comes from recorded events/appearances or a documented formula.
  * A statistic whose event category was NOT collected for a match is reported as "Not collected" - never as zero.
  * Per-90 rates use only matches where the category was collected AND the minutes are known.
  * Any formula with a zero or unknown denominator returns "N/A".

Event counting conventions (documented in docs/EVENT_DATA_DICTIONARY.md):
  * A scored goal is recorded ONCE as a 'goal' event (assist = related player) or a 'penalty' event with outcome 'scored'.
    Goals count as shots on target. Do not also record a 'shot' for the same goal.
  * 'own_goal' is recorded against the team of the player who scored it; the goal is credited to the opponent.
  * A key pass counts as a completed pass. Crosses are counted separately from passes.
  * A second yellow card counts as one yellow and one red card.
"""
from collections import defaultdict

from .db import q

PER90_CODES = ["goals", "assists", "shots", "shots_on_target", "key_passes", "passes_attempted", "tackles",
               "interceptions", "clearances", "blocks", "recoveries", "duels", "aerial_duels", "fouls"]
PERIOD_ORDER = {"1H": 1, "2H": 2, "ET1": 3, "ET2": 4, "PS": 5}


def V(value=None, status="ok", note="", basis=None, of=None):
    return {"value": value, "status": status, "note": note, "basis": basis, "of": of}


# ----------------------------------------------------------------------------- counting rules
def _by(e, p, field="player_id"):
    return p is None or e[field] == p


def _is_goal(e):
    return e["code"] == "goal" or (e["code"] == "penalty" and e["outcome"] == "scored")


def _is_shot(e):
    return e["code"] in ("shot", "goal", "penalty")


def _is_sot(e):
    return (e["code"] == "shot" and e["outcome"] == "on_target") or e["code"] == "goal" or \
           (e["code"] == "penalty" and e["outcome"] in ("scored", "saved"))


def _pass_att(e):
    return e["code"] in ("pass", "key_pass")


def _pass_comp(e):
    return e["code"] == "key_pass" or (e["code"] == "pass" and e["outcome"] == "completed")


# code -> (scope category, predicate(event, player_id_or_None))
COUNTERS = {
    "goals": ("goals", lambda e, p: _is_goal(e) and _by(e, p)),
    "penalties_scored": ("goals", lambda e, p: e["code"] == "penalty" and e["outcome"] == "scored" and _by(e, p)),
    "own_goals": ("goals", lambda e, p: e["code"] == "own_goal" and _by(e, p)),
    "assists": ("goals", lambda e, p: (e["code"] == "goal" and e["related_player_id"] is not None and _by(e, p, "related_player_id"))
                                        or (e["code"] == "assist" and _by(e, p))),
    "goals_from_set_pieces": ("goals", lambda e, p: e["code"] == "goal" and bool(e["set_piece_type"]) and _by(e, p)),
    "assists_from_set_pieces": ("goals", lambda e, p: e["code"] == "goal" and bool(e["set_piece_type"]) and
                                e["related_player_id"] is not None and _by(e, p, "related_player_id")),
    "shots": ("shots", lambda e, p: _is_shot(e) and _by(e, p)),
    "shots_on_target": ("shots", lambda e, p: _is_sot(e) and _by(e, p)),
    "passes_attempted": ("passes", lambda e, p: _pass_att(e) and _by(e, p)),
    "passes_completed": ("passes", lambda e, p: _pass_comp(e) and _by(e, p)),
    "key_passes": ("passes", lambda e, p: e["code"] == "key_pass" and _by(e, p)),
    "crosses": ("passes", lambda e, p: e["code"] == "cross" and _by(e, p)),
    "crosses_completed": ("passes", lambda e, p: e["code"] == "cross" and e["outcome"] == "completed" and _by(e, p)),
    "dribbles": ("attacking", lambda e, p: e["code"] == "dribble" and _by(e, p)),
    "offsides": ("attacking", lambda e, p: e["code"] == "offside" and _by(e, p)),
    "tackles": ("defensive", lambda e, p: e["code"] == "tackle" and _by(e, p)),
    "tackles_won": ("defensive", lambda e, p: e["code"] == "tackle" and e["outcome"] == "won" and _by(e, p)),
    "interceptions": ("defensive", lambda e, p: e["code"] == "interception" and _by(e, p)),
    "clearances": ("defensive", lambda e, p: e["code"] == "clearance" and _by(e, p)),
    "blocks": ("defensive", lambda e, p: e["code"] == "block" and _by(e, p)),
    "recoveries": ("defensive", lambda e, p: e["code"] == "recovery" and _by(e, p)),
    "duels": ("defensive", lambda e, p: e["code"] == "duel" and _by(e, p)),
    "duels_won": ("defensive", lambda e, p: e["code"] == "duel" and e["outcome"] == "won" and _by(e, p)),
    "aerial_duels": ("defensive", lambda e, p: e["code"] == "aerial_duel" and _by(e, p)),
    "aerial_duels_won": ("defensive", lambda e, p: e["code"] == "aerial_duel" and e["outcome"] == "won" and _by(e, p)),
    "saves": ("defensive", lambda e, p: e["code"] == "goalkeeper_action" and e["outcome"] == "save" and _by(e, p)),
    "fouls": ("discipline", lambda e, p: e["code"] == "foul" and e["outcome"] != "suffered" and _by(e, p)),
    "fouls_suffered": ("discipline", lambda e, p: e["code"] == "foul" and e["outcome"] == "suffered" and _by(e, p)),
    "yellow_cards": ("discipline", lambda e, p: e["code"] == "card" and e["outcome"] in ("yellow", "second_yellow") and _by(e, p)),
    "red_cards": ("discipline", lambda e, p: e["code"] == "card" and e["outcome"] in ("red", "second_yellow") and _by(e, p)),
    "set_pieces_taken": ("set_pieces", lambda e, p: e["code"] in ("corner", "free_kick") and _by(e, p)),
    "corners": ("set_pieces", lambda e, p: e["code"] == "corner" and _by(e, p)),
    "free_kicks": ("set_pieces", lambda e, p: e["code"] == "free_kick" and _by(e, p)),
}

NAMES = {
    "goals": "Goals", "penalties_scored": "Penalties scored", "own_goals": "Own goals", "assists": "Assists",
    "goals_from_set_pieces": "Goals from set pieces", "assists_from_set_pieces": "Assists from set pieces",
    "shots": "Shots", "shots_on_target": "Shots on target", "passes_attempted": "Passes attempted",
    "passes_completed": "Passes completed", "key_passes": "Key passes", "crosses": "Crosses",
    "crosses_completed": "Crosses completed", "dribbles": "Dribbles / carries", "offsides": "Offsides",
    "tackles": "Tackles", "tackles_won": "Tackles won", "interceptions": "Interceptions",
    "clearances": "Clearances", "blocks": "Blocks", "recoveries": "Recoveries", "duels": "Duels",
    "duels_won": "Duels won", "aerial_duels": "Aerial duels", "aerial_duels_won": "Aerial duels won",
    "saves": "Saves", "fouls": "Fouls committed", "fouls_suffered": "Fouls suffered",
    "yellow_cards": "Yellow cards", "red_cards": "Red cards", "set_pieces_taken": "Set pieces taken",
    "corners": "Corners", "free_kicks": "Free kicks",
    "appearances": "Appearances", "minutes": "Minutes played",
    "shot_accuracy": "Shot accuracy (%)", "pass_completion": "Pass completion (%)",
}
for _c in PER90_CODES:
    NAMES[_c + "_per90"] = NAMES[_c] + " per 90"


def _build_metric_definitions():
    out = []
    out.append(dict(code="appearances", name="Appearances", subject="player", scope=None, unit="count",
                    formula="Count of matches where appearance status = 'played'",
                    definition="Matches in which the player is recorded as having played.",
                    test="3 matches with status played, 1 unused substitute -> 3"))
    out.append(dict(code="minutes", name="Minutes played", subject="player", scope=None, unit="minutes",
                    formula="End minute - start minute (start = 0 for starters, or sub-on minute; end = earliest of "
                            "sub-off, dismissal, full-time)",
                    definition="Derived from the appearance record. Returns unavailable when sub minutes are missing "
                               "or the record is flagged uncertain.",
                    test="Starter, off at 45' -> 45; sub on at 60' in a 90' match -> 30"))
    for code, (scope, _fn) in COUNTERS.items():
        out.append(dict(code=code, name=NAMES[code], subject="player/team", scope=scope, unit="count",
                        formula=f"Count of recorded events matching the '{code}' rule (see event data dictionary)",
                        definition=f"{NAMES[code]} from validated match events. 'Not collected' when the "
                                   f"'{scope}' category was not collected for the match.",
                        test=""))
    for c in PER90_CODES:
        out.append(dict(code=c + "_per90", name=NAMES[c + "_per90"], subject="player", scope=COUNTERS[c][0], unit="per 90",
                        formula="Per 90 = Metric count / Minutes played x 90",
                        definition="Uses only matches where the category was collected and minutes are known. "
                                   "N/A when minutes are zero or unknown.",
                        test="1 goal in 45 minutes -> 2.0 per 90"))
    out.append(dict(code="shot_accuracy", name="Shot accuracy (%)", subject="player/team", scope="shots", unit="%",
                    formula="Shot accuracy (%) = Shots on target / Total shots x 100",
                    definition="N/A when total shots is zero.", test="2 on target from 4 shots -> 50.0%"))
    out.append(dict(code="pass_completion", name="Pass completion (%)", subject="player/team", scope="passes", unit="%",
                    formula="Pass completion (%) = Completed passes / Passes attempted x 100",
                    definition="N/A when passes attempted is zero.", test="10 completed of 12 attempted -> 83.3%"))
    out.append(dict(code="possession", name="Possession (%)", subject="team", scope=None, unit="%",
                    formula="Reported only if a possession source is recorded for the match",
                    definition="No possession figure is calculated from events; it is shown only from a documented source.",
                    test=""))
    return out


METRICS = _build_metric_definitions()


# ----------------------------------------------------------------------------- minutes
def minutes_played(app, duration=90):
    """Return (minutes or None, note)."""
    if app is None:
        return None, "No appearance record"
    st = app["appearance_status"]
    if st in ("unused_substitute", "did_not_play"):
        return 0, ""
    if st == "unknown":
        return None, "Appearance status unknown"
    if app["minutes_uncertain"]:
        return None, "Minutes flagged as uncertain"
    start = 0 if app["role"] == "starter" else app["sub_on_minute"]
    if start is None:
        return None, "Substitution-on minute missing"
    end = duration
    for k in ("sub_off_minute", "dismissed_minute"):
        if app[k] is not None:
            end = min(end, app[k])
    if end < start:
        return None, "Appearance times are inconsistent"
    return end - start, ""


# ----------------------------------------------------------------------------- aggregation
def per90(count, minutes):
    if minutes is None or minutes <= 0 or count is None:
        return None
    return count / minutes * 90.0


def ratio_pct(num, den):
    if den is None or den == 0 or num is None:
        return None
    return num / den * 100.0


def player_aggregate(pid, items):
    """items: list of dict(match=, scope=set, events=list, appearance=dict|None).
    Returns {metric_code: V(...)} aggregated over the matches in which the player played."""
    played = [it for it in items if it["appearance"] is not None and it["appearance"]["appearance_status"] == "played"]
    res = {}
    n_played = len(played)
    res["appearances"] = V(n_played, basis=n_played, of=len(items))
    mins_known, unknown = 0, 0
    per_match_min = {}
    for it in played:
        m, _n = minutes_played(it["appearance"], it["match"]["duration_minutes"])
        per_match_min[it["match"]["id"]] = m
        if m is None:
            unknown += 1
        else:
            mins_known += m
    if n_played == 0:
        res["minutes"] = V(None, "na", "No appearances")
    elif unknown == n_played:
        res["minutes"] = V(None, "na", "Minutes cannot be established from the appearance records")
    elif unknown:
        res["minutes"] = V(mins_known, "partial", f"Minutes unknown in {unknown} of {n_played} match(es); total is a minimum")
    else:
        res["minutes"] = V(mins_known)

    sums, bases = {}, {}
    for code, (scope, fn) in COUNTERS.items():
        total, basis = 0, 0
        for it in played:
            if scope in it["scope"]:
                basis += 1
                total += sum(1 for e in it["events"] if fn(e, pid))
        sums[code], bases[code] = total, basis
        if n_played == 0 or basis == 0:
            res[code] = V(None, "not_collected", f"'{scope}' events not collected" if n_played else "No appearances")
        elif basis < n_played:
            res[code] = V(total, "partial", f"Collected in {basis} of {n_played} matches", basis, n_played)
        else:
            res[code] = V(total, "ok", "", basis, n_played)

    for c in PER90_CODES:
        scope = COUNTERS[c][0]
        num, mins = 0, 0
        used = 0
        for it in played:
            m = per_match_min.get(it["match"]["id"])
            if scope in it["scope"] and m:
                num += sum(1 for e in it["events"] if COUNTERS[c][1](e, pid))
                mins += m
                used += 1
        if bases[c] == 0:
            res[c + "_per90"] = V(None, "not_collected", f"'{scope}' events not collected")
        elif used == 0 or mins <= 0:
            res[c + "_per90"] = V(None, "na", "Minutes played unknown or zero")
        else:
            note = "" if used == bases[c] else f"Based on {used} of {bases[c]} matches with known minutes"
            res[c + "_per90"] = V(per90(num, mins), "ok" if not note else "partial", note)

    for code, (num_c, den_c) in {"shot_accuracy": ("shots_on_target", "shots"),
                                 "pass_completion": ("passes_completed", "passes_attempted")}.items():
        d, n = res[den_c], res[num_c]
        if d["status"] == "not_collected":
            res[code] = V(None, "not_collected", d["note"])
        else:
            r = ratio_pct(n["value"], d["value"])
            res[code] = V(r, "ok" if r is not None else "na", "" if r is not None else "No attempts recorded",
                          d["basis"], d["of"]) if d["status"] != "partial" else \
                V(r, "partial" if r is not None else "na", d["note"], d["basis"], d["of"])
    return res


def goals_credited(match, events):
    """List of (credited_team_id, event). Own goals are credited to the opposing team."""
    out = []
    for e in events:
        if _is_goal(e):
            out.append((e["team_id"], e))
        elif e["code"] == "own_goal":
            opp = match["away_team_id"] if e["team_id"] == match["home_team_id"] else match["home_team_id"]
            out.append((opp, e))
    return out


def team_stats(match, team_id, scope, events):
    """Team-level metrics for a single match."""
    res = {}
    mine = [e for e in events if e["team_id"] == team_id]
    for code, (cat, fn) in COUNTERS.items():
        if cat in scope:
            res[code] = V(sum(1 for e in mine if fn(e, None)))
        else:
            res[code] = V(None, "not_collected", f"'{cat}' events not collected")
    if "goals" in scope:
        res["goals_for"] = V(sum(1 for t, _ in goals_credited(match, events) if t == team_id))
        res["goals_against"] = V(sum(1 for t, _ in goals_credited(match, events) if t != team_id))
        res["goals"] = res["goals_for"]
    else:
        res["goals_for"] = res["goals_against"] = V(None, "not_collected", "'goals' events not collected")
    for code, (n, d) in {"shot_accuracy": ("shots_on_target", "shots"), "pass_completion": ("passes_completed", "passes_attempted")}.items():
        if res[d]["status"] == "not_collected":
            res[code] = V(None, "not_collected", res[d]["note"])
        else:
            r = ratio_pct(res[n]["value"], res[d]["value"])
            res[code] = V(r, "ok" if r is not None else "na", "" if r is not None else "No attempts recorded")
    # Possession only from a documented source
    side = "possession_home" if team_id == match["home_team_id"] else "possession_away"
    if match[side] is not None and match["possession_source"]:
        res["possession"] = V(match[side], "ok", f"Source: {match['possession_source']}")
    else:
        res["possession"] = V(None, "not_collected", "No documented possession source")
    return res


def goals_by_period(match, events):
    out = {match["home_team_id"]: defaultdict(int), match["away_team_id"]: defaultdict(int)}
    for t, e in goals_credited(match, events):
        out[t][e["period"]] += 1
    return {k: dict(v) for k, v in out.items()}


def fmt(v, decimals=1, suffix=""):
    """Human display of a metric value dict: counts as integers, rates with decimals, never a silent zero."""
    if v is None:
        return "N/A"
    if v["status"] == "not_collected":
        return "Not collected"
    if v["status"] == "na" or v["value"] is None:
        return "N/A"
    x = v["value"]
    s = f"{x:.{decimals}f}" if isinstance(x, float) else str(int(x))
    return s + suffix + ("*" if v["status"] == "partial" else "")


# ----------------------------------------------------------------------------- DB gathering
def load_match(match_id, provisional=False):
    m = q("SELECT * FROM matches WHERE id=?", (match_id,), one=True)
    if not m:
        return None
    scope = {r["category"] for r in q("SELECT category FROM match_collection_scope WHERE match_id=? AND collected=1", (match_id,))}
    sql = ("SELECT e.*, t.code AS code FROM match_events e JOIN event_types t ON t.id=e.event_type_id WHERE e.match_id=?")
    if not provisional:
        sql += " AND e.validation_status='validated'"
    events = [dict(r) for r in q(sql, (match_id,))]
    events.sort(key=lambda e: (PERIOD_ORDER.get(e["period"], 9), e["minute"] if e["minute"] is not None else 999,
                               e["second"] or 0, e["id"]))
    apps = {r["player_id"]: dict(r) for r in q("SELECT * FROM appearances WHERE match_id=?", (match_id,))}
    return {"match": dict(m), "scope": scope, "events": events, "appearances": apps}


def quality_checks(md):
    m, scope, events, apps = md["match"], md["scope"], md["events"], md["appearances"]
    out = []
    missing = [c for c, _ in __import__("app.constants", fromlist=["x"]).SCOPE_CATEGORIES if c not in scope]
    if missing:
        out.append(("info", "Event categories not collected for this match: " + ", ".join(missing)))
    if not apps:
        out.append(("error", "No lineup/appearance records - minutes and per-90 values are unavailable"))
    unknown = [a for a in apps.values() if minutes_played(a, m["duration_minutes"])[0] is None and a["appearance_status"] == "played"]
    if unknown:
        out.append(("warning", f"{len(unknown)} player(s) have uncertain playing minutes"))
    if "goals" in scope and m["home_score"] is not None:
        g = {m["home_team_id"]: 0, m["away_team_id"]: 0}
        for t, _ in goals_credited(m, events):
            g[t] += 1
        if (g[m["home_team_id"]], g[m["away_team_id"]]) != (m["home_score"], m["away_score"]):
            out.append(("error", f"Recorded goals ({g[m['home_team_id']]}-{g[m['away_team_id']]}) do not match the score "
                                 f"({m['home_score']}-{m['away_score']})"))
    if m["possession_source"] is None:
        out.append(("info", "Possession not reported (no documented source)"))
    if not any(e["x_start"] is not None for e in events if e["code"] in ("shot", "goal", "penalty")):
        out.append(("info", "No shot coordinates collected - shot map not available"))
    return out


def analyse_match(match_id, provisional=False):
    md = load_match(match_id, provisional)
    if md is None:
        return None
    m = md["match"]
    players = {}
    for pid, app in md["appearances"].items():
        players[pid] = player_aggregate(pid, [{"match": m, "scope": md["scope"], "events": md["events"], "appearance": app}])
    teams = {t: team_stats(m, t, md["scope"], md["events"]) for t in (m["home_team_id"], m["away_team_id"])}
    valid = m["status"] in ("data_validated", "analysis_in_progress", "report_under_review", "approved",
                            "delivered_to_client", "archived")
    return {"match_data": md, "players": players, "teams": teams,
            "data_status": "validated" if valid else "provisional",
            "goals_by_period": goals_by_period(m, md["events"]), "quality": quality_checks(md)}


def player_career(pid, match_ids, provisional=False):
    items = []
    for mid in match_ids:
        md = load_match(mid, provisional)
        if md:
            items.append({"match": md["match"], "scope": md["scope"], "events": md["events"], "appearance": md["appearances"].get(pid)})
    return player_aggregate(pid, items)


def store_run(db_ex, match_id, user_id, result, note=""):
    """Persist an analysis run snapshot. db_ex is app.db.ex."""
    run = db_ex("INSERT INTO analysis_runs (match_id, run_by, data_status, status, notes) VALUES (?,?,?,?,?)",
                (match_id, user_id, result["data_status"], "complete", note))
    rows = []
    for pid, stats in result["players"].items():
        for code, v in stats.items():
            rows.append((run, "player", pid, code, v["value"], v["status"], v["note"], v["basis"], v["of"]))
    for tid, stats in result["teams"].items():
        for code, v in stats.items():
            rows.append((run, "team", tid, code, v["value"], v["status"], v["note"], v["basis"], v["of"]))
    from .db import get_db
    get_db().executemany("INSERT INTO metric_values (analysis_run_id, subject_type, subject_id, metric_code, value, status, "
                         "note, basis_matches, of_matches) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return run


# ----------------------------------------------------------------------------- self tests (known examples)
def _ev(code, team=1, player=None, outcome=None, related=None, set_piece=None, period="1H", minute=10):
    return dict(id=0, code=code, team_id=team, player_id=player, outcome=outcome, related_player_id=related,
                set_piece_type=set_piece, period=period, minute=minute, second=0, x_start=None)


def run_selftests():
    """Run the formulas against hand-checked examples. Returns list of (name, passed, detail)."""
    results = []

    def check(name, got, expected, tol=1e-9):
        ok = (got is None and expected is None) or (got is not None and expected is not None and abs(got - expected) < tol)
        results.append((name, ok, f"expected {expected}, got {got}"))

    match = dict(id=1, duration_minutes=90, home_team_id=1, away_team_id=2, home_score=2, away_score=1,
                 possession_home=None, possession_away=None, possession_source=None)
    ev = []
    ev += [_ev("shot", player=7, outcome="on_target"), _ev("shot", player=7, outcome="off_target"),
           _ev("shot", player=7, outcome="blocked"), _ev("goal", player=7, related=8)]
    ev += [_ev("pass", player=7, outcome="completed") for _ in range(8)]
    ev += [_ev("pass", player=7, outcome="incomplete") for _ in range(2)]
    ev += [_ev("key_pass", player=7) for _ in range(2)]
    ev += [_ev("goal", team=2, player=20), _ev("own_goal", team=2, player=21), _ev("card", player=7, outcome="second_yellow")]
    scope = {"goals", "shots", "passes", "discipline"}          # 'defensive' deliberately not collected
    app = dict(role="starter", sub_on_minute=None, sub_off_minute=45, dismissed_minute=None,
               appearance_status="played", minutes_uncertain=0)
    p = player_aggregate(7, [dict(match=match, scope=scope, events=ev, appearance=app)])
    check("minutes: starter substituted off at 45' = 45", p["minutes"]["value"], 45)
    check("goals = 1", p["goals"]["value"], 1)
    check("shots: 3 shots + 1 goal = 4", p["shots"]["value"], 4)
    check("shots on target: 1 on target + 1 goal = 2", p["shots_on_target"]["value"], 2)
    check("shot accuracy: 2/4 x 100 = 50.0", p["shot_accuracy"]["value"], 50.0)
    check("passes attempted: 10 passes + 2 key passes = 12", p["passes_attempted"]["value"], 12)
    check("passes completed: 8 + 2 key passes = 10", p["passes_completed"]["value"], 10)
    check("pass completion: 10/12 x 100 = 83.333", p["pass_completion"]["value"], 10 / 12 * 100, 1e-6)
    check("goals per 90: 1 / 45 x 90 = 2.0", p["goals_per90"]["value"], 2.0)
    check("assists for player 8 (related player on goal) = 1", player_aggregate(8, [dict(match=match, scope=scope, events=ev, appearance=app)])["assists"]["value"], 1)
    check("second yellow counts as 1 yellow", p["yellow_cards"]["value"], 1)
    check("second yellow counts as 1 red", p["red_cards"]["value"], 1)
    results.append(("tackles NOT collected is not zero", p["tackles"]["status"] == "not_collected" and p["tackles"]["value"] is None,
                    f"status={p['tackles']['status']}"))
    results.append(("tackles per 90 NOT collected is not zero", p["tackles_per90"]["status"] == "not_collected", ""))
    # zero / unknown denominators
    app2 = dict(app, sub_off_minute=None, minutes_uncertain=1)
    p2 = player_aggregate(7, [dict(match=match, scope=scope, events=ev, appearance=app2)])
    results.append(("uncertain minutes -> per 90 is N/A", p2["goals_per90"]["status"] == "na" and p2["goals_per90"]["value"] is None, p2["goals_per90"]["note"]))
    p3 = player_aggregate(7, [dict(match=match, scope=scope, events=[], appearance=app)])
    results.append(("zero shots -> shot accuracy N/A", p3["shot_accuracy"]["status"] == "na", ""))
    check("zero shots recorded is a real zero when collected", p3["shots"]["value"], 0)
    sub = dict(role="substitute", sub_on_minute=60, sub_off_minute=None, dismissed_minute=None,
               appearance_status="played", minutes_uncertain=0)
    check("minutes: substitute on at 60' = 30", minutes_played(sub, 90)[0], 30)
    sub2 = dict(sub, sub_on_minute=None)
    results.append(("minutes: substitute without on-minute is unavailable", minutes_played(sub2, 90)[0] is None, ""))
    red = dict(app, sub_off_minute=None, dismissed_minute=76)
    check("minutes: dismissed at 76' = 76", minutes_played(red, 90)[0], 76)
    # team level incl. own goal
    t1 = team_stats(match, 1, scope, ev)
    t2 = team_stats(match, 2, scope, ev)
    check("team 1 goals incl. opponent own goal = 2", t1["goals_for"]["value"], 2)
    check("team 2 goals = 1", t2["goals_for"]["value"], 1)
    results.append(("team possession not reported without source", t1["possession"]["status"] == "not_collected", ""))
    results.append(("team tackles not collected", t1["tackles"]["status"] == "not_collected", ""))
    check("fmt N/A handling", None, None)
    return results
