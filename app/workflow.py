"""Match workflow transitions and automated data validation."""
from collections import defaultdict

from . import constants as C
from .db import ex, q, scalar
from .metrics import goals_credited, load_match, minutes_played
from .security import audit

SINGULAR_TYPES = {"goal", "card", "penalty", "own_goal", "substitution"}


def set_status(match_id, new, user_id=None, note=""):
    m = q("SELECT status FROM matches WHERE id=?", (match_id,), one=True)
    if not m or m["status"] == new:
        return
    ex("UPDATE matches SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, match_id))
    ex("INSERT INTO match_status_history (match_id, old_status, new_status, user_id, note) VALUES (?,?,?,?,?)",
       (match_id, m["status"], new, user_id, note))
    audit("match.status", "matches", match_id, {"from": m["status"], "to": new, "note": note})


def can_collect(user_id, match_id):
    return scalar("SELECT COUNT(*) FROM collection_assignments WHERE match_id=? AND user_id=? "
                  "AND assignment_role IN ('collector','backup_collector') AND status!='cancelled'",
                  (match_id, user_id)) > 0


def is_assigned(user_id, match_id, roles=None):
    sql = "SELECT COUNT(*) FROM collection_assignments WHERE match_id=? AND user_id=?"
    args = [match_id, user_id]
    if roles:
        sql += " AND assignment_role IN (%s)" % ",".join("?" * len(roles))
        args += list(roles)
    return scalar(sql, args) > 0


def _issue(issues, match_id, itype, severity, msg, event_id=None):
    issues.append((match_id, event_id, itype, severity, msg[:255]))


def run_validation(match_id, user_id=None):
    """Re-run automated checks. Replaces previous open automated issues; keeps manually raised and ignored ones."""
    md = load_match(match_id, provisional=True)
    m, scope, events, apps = md["match"], md["scope"], md["events"], md["appearances"]
    events = [e for e in events if e["validation_status"] != "draft"] or events
    types = {r["code"]: dict(r) for r in q("SELECT * FROM event_types")}
    issues = []
    names = {r["id"]: r["full_name"] for r in q("SELECT id, full_name FROM players")}

    if not scope:
        _issue(issues, match_id, "scope", "error", "No collection scope declared - say which event categories were collected for this match.")
    if not events:
        _issue(issues, match_id, "no_events", "error", "No events have been submitted for this match.")
    for team in (m["home_team_id"], m["away_team_id"]):
        if not any(a["team_id"] == team for a in apps.values()):
            _issue(issues, match_id, "lineup", "error", "No lineup/appearance records for one team (team id %d)." % team)
    if m["home_score"] is None or m["away_score"] is None:
        _issue(issues, match_id, "score", "error", "Official final score has not been entered.")
    elif "goals" in scope:
        g = defaultdict(int)
        for t, _e in goals_credited(m, events):
            g[t] += 1
        hs, as_ = g[m["home_team_id"]], g[m["away_team_id"]]
        if (hs, as_) != (m["home_score"], m["away_score"]):
            _issue(issues, match_id, "score", "error",
                   f"Score mismatch: official {m['home_score']}-{m['away_score']} but recorded goals give {hs}-{as_}.")

    seen = {}
    for e in events:
        t = types.get(e["code"])
        label = f"#{e['id']} {t['name'] if t else e['code']}"
        if e["team_id"] not in (m["home_team_id"], m["away_team_id"]):
            _issue(issues, match_id, "team", "error", f"{label}: team is not playing in this match.", e["id"])
        if t and t["needs_player"] and e["player_id"] is None:
            _issue(issues, match_id, "missing", "error", f"{label}: player missing.", e["id"])
        if t and t["outcomes"] and not e["outcome"]:
            _issue(issues, match_id, "missing", "error", f"{label}: outcome missing.", e["id"])
        if e["minute"] is None:
            _issue(issues, match_id, "time", "warning", f"{label}: match minute missing.", e["id"])
        elif e["minute"] < 0 or e["minute"] > 150:
            _issue(issues, match_id, "time", "error", f"{label}: minute {e['minute']} is outside the possible range.", e["id"])
        pid = e["player_id"]
        if pid is not None and e["code"] not in ("substitution",):
            a = apps.get(pid)
            nm = names.get(pid, pid)
            if a is None:
                _issue(issues, match_id, "player_link", "error", f"{label}: {nm} has no appearance record in this match.", e["id"])
            else:
                if a["team_id"] != e["team_id"] and e["code"] != "own_goal":
                    _issue(issues, match_id, "player_link", "error", f"{label}: {nm} is recorded for a different team.", e["id"])
                if e["minute"] is not None and a["appearance_status"] == "played" and e["code"] not in ("period_start", "period_end"):
                    start = 0 if a["role"] == "starter" else a["sub_on_minute"]
                    end = m["duration_minutes"] + 30
                    for k in ("sub_off_minute", "dismissed_minute"):
                        if a[k] is not None:
                            end = min(end, a[k])
                    if start is not None and (e["minute"] < start - 1 or e["minute"] > end + 1):
                        _issue(issues, match_id, "player_time", "warning",
                               f"{label} at {e['minute']}': {nm} was not on the pitch (on {start}', off {end if end < 999 else '-'}').", e["id"])
                if a["appearance_status"] in ("unused_substitute", "did_not_play"):
                    _issue(issues, match_id, "player_link", "error", f"{label}: {nm} is marked as not having played.", e["id"])
        # duplicates
        if e["minute"] is not None:
            if e["second"] is not None:
                key = (e["code"], e["team_id"], pid, e["period"], e["minute"], e["second"], e["outcome"])
            elif e["code"] in SINGULAR_TYPES:
                key = (e["code"], e["team_id"], pid, e["period"], e["minute"], None, e["outcome"])
            else:
                key = None
            if key:
                if key in seen:
                    _issue(issues, match_id, "duplicate", "warning",
                           f"{label}: likely duplicate of event #{seen[key]} (same type, player and time).", e["id"])
                else:
                    seen[key] = e["id"]
        if e["code"] == "card" and e["outcome"] in ("red", "second_yellow") and pid in apps and apps[pid]["dismissed_minute"] is None:
            _issue(issues, match_id, "dismissal", "warning", f"{label}: red card recorded but no dismissal minute in the lineup.", e["id"])
        if e["code"] == "assist":
            for g in events:
                if g["code"] == "goal" and g["related_player_id"] == pid and g["minute"] == e["minute"] and g["team_id"] == e["team_id"]:
                    _issue(issues, match_id, "assist_double", "warning",
                           f"{label}: assist is also recorded on goal #{g['id']} - it would be counted twice.", e["id"])
                    break

    # Replace open automated issues; keep manual and ignored ones
    ignored = {(r["issue_type"], r["event_id"], r["message"]) for r in
               q("SELECT issue_type, event_id, message FROM validation_issues WHERE match_id=? AND status='ignored'", (match_id,))}
    ex("DELETE FROM validation_issues WHERE match_id=? AND status='open' AND raised_by IS NULL", (match_id,))
    n = 0
    for (mid, eid, itype, sev, msg) in issues:
        if (itype, eid, msg) in ignored:
            continue
        ex("INSERT INTO validation_issues (match_id, event_id, issue_type, severity, message, raised_by) VALUES (?,?,?,?,?,NULL)",
           (mid, eid, itype, sev, msg))
        n += 1
    return n


def open_error_count(match_id):
    return scalar("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND status='open' AND severity='error'", (match_id,))
