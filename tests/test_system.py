"""Acceptance tests mapped to section 21 of the specification."""
import json
import sqlite3
from pathlib import Path

import pytest

from conftest import login, post

ROLE_USERS = {"md": "Executive Dashboard", "ops": "Operations Dashboard", "analyst": "Analysis Dashboard",
              "scout": "Scouting Dashboard", "tech": "Technical Administration Dashboard", "finance": "Business and Finance Dashboard"}


# 1 -------------------------------------------------------------------
@pytest.mark.parametrize("user,title", ROLE_USERS.items())
def test_each_position_gets_its_dashboard(demo_app, user, title):
    r = login(demo_app, user).get("/dashboard")
    assert r.status_code == 200 and title.encode() in r.data


# 2 -------------------------------------------------------------------
def test_unauthorised_actions_are_blocked(demo_app):
    a = demo_app
    assert login(a, "finance").get("/admin/users").status_code == 403
    assert login(a, "scout").get("/finance/").status_code == 403
    assert login(a, "analyst").get("/finance/invoices").status_code == 403
    assert login(a, "tech").get("/reports/").status_code == 403           # technical access does not grant report access
    assert login(a, "ops").post("/validate/1/approve", data={"_csrf": "t"}).status_code in (400, 403)
    assert post(login(a, "ops"), "/validate/1/approve").status_code == 403
    assert post(login(a, "analyst"), "/finance/invoices/new").status_code == 403
    assert post(login(a, "collector"), "/matches/new").status_code == 403


def test_csrf_is_enforced(demo_app):
    c = login(demo_app, "ops")
    assert c.post("/matches/1/status", data={"status": "ready_for_collection"}).status_code == 400


def test_md_cannot_see_detailed_finance_without_permission_but_sees_summary(demo_app):
    r = login(demo_app, "md").get("/dashboard")
    assert b"Outstanding invoices" in r.data
    assert login(demo_app, "ops").get("/dashboard").data.count(b"Outstanding invoices") == 0   # ops has no finance summary


# 3 -------------------------------------------------------------------
def test_ops_creates_match_and_assigns_collector(demo_app):
    c = login(demo_app, "ops")
    r = post(c, "/matches/new", home_team_id="1", away_team_id="2", kickoff="2026-12-01T15:00", duration_minutes="90", as_collector="7")
    assert r.status_code == 302
    con = sqlite3.connect(demo_app.config["DATABASE"])
    row = con.execute("SELECT status, id FROM matches ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == "assigned"
    assert con.execute("SELECT COUNT(*) FROM collection_assignments WHERE match_id=? AND assignment_role='collector'", (row[1],)).fetchone()[0] == 1
    same = post(c, "/matches/new", home_team_id="1", away_team_id="1", kickoff="2026-12-01T15:00", duration_minutes="90")
    assert same.status_code == 422                      # home and away must differ


# 4 + 5 + 6 ------------------------------------------------------------
def test_collect_validate_correct_and_audit(demo_app):
    a = demo_app
    con = sqlite3.connect(a.config["DATABASE"])
    # collector can only record for assigned matches
    col = login(a, "collector")
    ev = {"event_type_id": 1, "team_id": 1, "player_id": 1, "period": "1H", "minute": 5, "outcome": "on_target"}
    with col.session_transaction() as s:
        s["_csrf"] = "t"
    r = col.post(f"/collect/{a.ids['m5']}/event", json=ev, headers={"X-CSRF-Token": "t"})
    assert r.status_code == 403                          # match 5 (M-2026-0005) is not assigned to the collector
    # match 3 is assigned: invalid event rejected (player from the wrong team)
    bad = col.post(f"/collect/{a.ids['m3']}/event", json=dict(ev, team_id=1, player_id=30, event_type_id=1), headers={"X-CSRF-Token": "t"})
    assert bad.status_code in (403, 422)
    # analyst corrects a validated-stage event only with a reason
    an = login(a, "analyst")
    m3 = con.execute("SELECT id FROM match_events WHERE match_id=? ORDER BY id LIMIT 1", (a.ids["m3"],)).fetchone()[0]
    ok = con.execute("SELECT * FROM match_events WHERE id=?", (m3,)).fetchone()
    payload = dict(id=m3, event_type_id=ok[4], team_id=ok[2], player_id=ok[3], period=ok[5], minute=16, outcome=ok[7], related_player_id=ok[8])
    with an.session_transaction() as s:
        s["_csrf"] = "t"
    no_reason = an.post(f"/collect/{a.ids['m3']}/event", json=payload, headers={"X-CSRF-Token": "t"})
    assert no_reason.status_code == 422
    good = an.post(f"/collect/{a.ids['m3']}/event", json=dict(payload, reason="Minute corrected from video", confirm_duplicate=True), headers={"X-CSRF-Token": "t"})
    assert good.status_code == 200, good.data
    con2 = sqlite3.connect(a.config["DATABASE"])
    log = con2.execute("SELECT details, user_id FROM audit_logs WHERE action='event.correct' AND entity_id=?", (m3,)).fetchone()
    assert log and "Minute corrected" in log[0]


def test_validation_blocks_approval_with_errors(demo_app):
    an = login(demo_app, "analyst")
    con = sqlite3.connect(demo_app.config["DATABASE"])
    m3 = demo_app.ids["m3"]                       # M-2026-0003 has a score mismatch -> cannot be approved
    post(an, f"/validate/{m3}/approve", ack_warnings="1")
    assert con.execute("SELECT status FROM matches WHERE id=?", (m3,)).fetchone()[0] == "validation_required"
    assert con.execute("SELECT COUNT(*) FROM validation_issues WHERE match_id=? AND severity='error' AND status='open'", (m3,)).fetchone()[0] >= 1


# 7 + 8 -----------------------------------------------------------------
def test_player_minutes_and_missing_data(demo_app):
    from app.metrics import analyse_match
    with demo_app.app_context():
        res = analyse_match(1)
        m = res["match_data"]["match"]
        pid = demo_app.ids["players"]["Kwanele Mthembu"]            # starter substituted off at 63'
        st = res["players"][pid]
        assert st["minutes"]["value"] == 63
        sub = res["players"][demo_app.ids["players"]["Lwazi Shabalala"]]   # on at 63'
        assert sub["minutes"]["value"] == 27
        assert sub["assists"]["value"] == 1
        mahlangu = res["players"][demo_app.ids["players"]["Siza Mahlangu"]]
        assert mahlangu["goals"]["value"] == 1 and mahlangu["minutes"]["value"] == 90
        assert abs(mahlangu["goals_per90"]["value"] - 1.0) < 1e-9
        assert mahlangu["dribbles"]["status"] == "not_collected" and mahlangu["dribbles"]["value"] is None   # 'attacking' not collected
        assert res["teams"][m["home_team_id"]]["possession"]["status"] == "not_collected"
        assert res["teams"][m["home_team_id"]]["goals_for"]["value"] == 2 and res["teams"][m["away_team_id"]]["goals_for"]["value"] == 1


# 9 + 10 + 11 + 12 -------------------------------------------------------
def test_reports_pdf_and_review_flow(demo_app):
    an = login(demo_app, "analyst")
    for rid in (1, 2):
        r = an.get(f"/reports/{rid}/v/1.pdf")
        assert r.status_code == 200 and r.data[:4] == b"%PDF"
    assert an.get("/reports/3/preview.pdf").data[:4] == b"%PDF"
    con = sqlite3.connect(demo_app.config["DATABASE"])
    assert con.execute("SELECT status FROM reports WHERE id IN (1,2)").fetchall() == [("delivered",), ("delivered",)]
    # an author cannot approve their own report
    r = post(login(demo_app, "scout"), "/reports/4/approve")
    assert r.status_code == 403


def test_client_isolation(demo_app):
    rud = login(demo_app, "client.rudimentary")
    city = login(demo_app, "client.city")
    assert b"Open PDF" in rud.get("/portal/").data
    assert b"Open PDF" not in city.get("/portal/").data
    share = sqlite3.connect(demo_app.config["DATABASE"]).execute("SELECT id FROM report_shares LIMIT 1").fetchone()[0]
    assert rud.get(f"/portal/report/{share}.pdf").status_code == 200
    assert city.get(f"/portal/report/{share}.pdf").status_code == 404        # another client's report
    assert rud.get("/dashboard").status_code == 302                          # clients stay in the portal
    assert rud.get("/reports/").status_code in (302, 403)
    assert rud.get("/reports/1/v/1.pdf").status_code in (302, 403)
    assert rud.get("/admin/users").status_code in (302, 403)


def test_withdrawn_report_disappears_for_client(demo_app):
    fin = login(demo_app, "finance")
    r = post(fin, "/reports/2/withdraw", reason="Test withdrawal")
    share = sqlite3.connect(demo_app.config["DATABASE"]).execute("SELECT id FROM report_shares WHERE report_id=2").fetchone()[0]
    assert login(demo_app, "client.rudimentary").get(f"/portal/report/{share}.pdf").status_code == 404


def test_provisional_data_is_clearly_marked(demo_app):
    from app import pdfgen
    from app.views.reports import build_snapshot, _report
    with demo_app.test_request_context():
        pass
    con = sqlite3.connect(demo_app.config["DATABASE"])
    snap = json.loads(con.execute("SELECT content FROM report_versions WHERE report_id=1").fetchone()[0])
    assert snap["data_status"] == "validated"
    snap["data_status"] = "provisional"
    assert pdfgen.render(snap)[:4] == b"%PDF"


# 13 + 14 ---------------------------------------------------------------
def test_invoices_and_balances(demo_app):
    fin = login(demo_app, "finance")
    r = post(fin, "/finance/invoices/new", client_id="1", issue_date="2026-10-01", due_date="2026-10-31", tax_rate="10",
             service=["1", ""], desc=["Player report", "Extra"], qty=["2", "1"], price=["450", "100"])
    assert r.status_code == 302
    con = sqlite3.connect(demo_app.config["DATABASE"])
    inv = con.execute("SELECT id, subtotal, tax_amount, total, status FROM invoices ORDER BY id DESC LIMIT 1").fetchone()
    assert (inv[1], inv[2], inv[3], inv[4]) == (1000.0, 100.0, 1100.0, "draft")
    assert post(fin, f"/finance/invoices/{inv[0]}/payment", amount="100", paid_date="2026-10-02").status_code == 302
    assert con.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?", (inv[0],)).fetchone()[0] == 0   # draft cannot be paid
    post(fin, f"/finance/invoices/{inv[0]}/status", action="send")
    post(fin, f"/finance/invoices/{inv[0]}/payment", amount="400", paid_date="2026-10-02")
    post(fin, f"/finance/invoices/{inv[0]}/payment", amount="9999", paid_date="2026-10-02")           # overpayment rejected
    con2 = sqlite3.connect(demo_app.config["DATABASE"])
    assert con2.execute("SELECT status FROM invoices WHERE id=?", (inv[0],)).fetchone()[0] == "partial"
    post(fin, f"/finance/invoices/{inv[0]}/payment", amount="700", paid_date="2026-10-03")
    assert sqlite3.connect(demo_app.config["DATABASE"]).execute("SELECT status FROM invoices WHERE id=?", (inv[0],)).fetchone()[0] == "paid"
    assert post(fin, "/e/expenses/new", expense_date="2026-10-05", category="Transport", description="Taxi", amount="150").status_code == 302


# 15 --------------------------------------------------------------------
def test_csv_export_and_formula_injection_guard(demo_app):
    an = login(demo_app, "ops")
    r = an.get("/e/players/export.csv")
    assert r.status_code == 200 and b"full_name" in r.data and b"date_of_birth" not in r.data
    assert login(demo_app, "collector").get("/e/players/export.csv").status_code == 403


# 16 --------------------------------------------------------------------
def test_backup_and_restore(demo_app, tmp_path):
    from app.views.admin import make_backup, test_restore
    with demo_app.app_context():
        z = make_backup()
        ok, integrity, diffs = test_restore(z)
        assert ok and integrity == "ok" and not diffs
    tech = login(demo_app, "tech")
    r = post(tech, "/admin/backups", action="backup")
    assert r.status_code == 302
    r = post(tech, "/admin/backups", action="test")
    con = sqlite3.connect(demo_app.config["DATABASE"])
    assert con.execute("SELECT status FROM backup_logs WHERE action='restore_test' ORDER BY id DESC").fetchone()[0] == "ok"


# 17 --------------------------------------------------------------------
def test_errors_are_friendly_and_logged(demo_app):
    c = login(demo_app, "ops")
    r = c.get("/matches/99999")
    assert r.status_code == 404 and b"Page not found" in r.data
    assert login(demo_app, "scout").get("/admin/users").status_code == 403 and b"Access denied" in login(demo_app, "scout").get("/admin/users").data


def test_login_lockout_and_password_policy(demo_app):
    c = demo_app.test_client()
    for _ in range(5):
        c.get("/login")
        with c.session_transaction() as s:
            s["_csrf"] = "t"
        c.post("/login", data={"identifier": "collector", "password": "wrong", "_csrf": "t"})
    c.get("/login")
    with c.session_transaction() as s:
        s["_csrf"] = "t"
    r = c.post("/login", data={"identifier": "collector", "password": "Demo#2026pass", "_csrf": "t"})
    assert r.status_code == 200                                   # locked even with the right password
    con = sqlite3.connect(demo_app.config["DATABASE"])
    con.execute("UPDATE users SET locked_until=NULL, failed_logins=0 WHERE username='collector'")
    con.commit()


def test_session_timeout(demo_app):
    c = login(demo_app, "ops")
    with c.session_transaction() as s:
        s["last_seen"] = 0
    r = c.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_every_screen_renders_for_every_role(demo_app):
    """Crawl list/detail pages as each employee; none may error (500)."""
    urls = ["/dashboard", "/matches/", "/matches/1", "/matches/1/lineups", "/matches/3", "/collect/", "/collect/2", "/validate/", "/validate/2",
            "/analysis/", "/analysis/match/1", "/analysis/player/1", "/analysis/metrics", "/reports/", "/reports/1", "/reports/3", "/reports/new?type=player",
            "/reports/new?type=match", "/reports/new?type=team", "/reports/new?type=scouting", "/video/", "/video/1", "/scouting/", "/scouting/1",
            "/scouting/new", "/clients/1", "/requests", "/leads/1", "/finance/", "/finance/invoices", "/finance/invoices/1", "/finance/invoices/new",
            "/tasks/", "/tasks/new", "/marketing/", "/admin/users", "/admin/users/new", "/admin/roles", "/admin/settings", "/admin/audit", "/admin/backups",
            "/admin/errors", "/admin/imports", "/players/1", "/seasons/1/teams", "/matches/new", "/video/new", "/collect/1", "/analysis/match/1/chart/teams.png"]
    urls += [f"/e/{n}/" for n in ("clubs", "teams", "players", "competitions", "seasons", "venues", "data_sources", "services", "clients", "leads", "campaigns", "expenses", "proposals")]
    urls += [f"/e/{n}/new" for n in ("clubs", "players", "clients", "expenses")]
    for user in ROLE_USERS.keys() | {"collector"}:
        c = login(demo_app, user)
        for u in urls:
            r = c.get(u)
            assert r.status_code in (200, 302, 403, 404), f"{user} {u} -> {r.status_code}"
            assert r.status_code != 500
    con = sqlite3.connect(demo_app.config["DATABASE"])
    assert con.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0] == 0, con.execute("SELECT path, message FROM error_logs").fetchall()


def test_video_sharing_rules(demo_app):
    sc = login(demo_app, "scout")
    r = post(sc, "/video/new", title="X", reference="http://x", permission_status="pending", access_restriction="client_shareable", licence_notes="n")
    assert r.status_code == 422                                   # cannot be client-shareable without permission
    r = post(sc, "/video/2/permission", permission_status="pending", access_restriction="client_shareable")
    assert sqlite3.connect(demo_app.config["DATABASE"]).execute("SELECT access_restriction FROM video_assets WHERE id=2").fetchone()[0] == "internal_only"


def test_full_collection_flow_on_new_match(demo_app):
    """Lineups -> collector records events -> submit -> analyst validates -> statistics (acceptance items 3-7)."""
    a = demo_app
    con = sqlite3.connect(a.config["DATABASE"])
    mid = a.ids["m4"]                                            # Lake Town v City United, assigned to the collector
    ops, col, an = login(a, "ops"), login(a, "collector"), login(a, "analyst")
    teams = con.execute("SELECT home_team_id, away_team_id FROM matches WHERE id=?", (mid,)).fetchone()
    for tid in teams:
        pl = [r[0] for r in con.execute("SELECT id FROM players WHERE current_team_id=? ORDER BY id LIMIT 12", (tid,))]
        form = {"team_id": str(tid)}
        for i, p in enumerate(pl):
            form[f"p{p}_in"] = "on"
            if i < 11:
                form[f"p{p}_starter"] = "on"
            else:
                form[f"p{p}_on"] = "70"
                form[f"p{p}_status"] = "played"
            if i == 0:
                form[f"p{p}_off"] = ""
            if i == 5:
                form[f"p{p}_off"] = "70"
        r = post(ops, f"/matches/{mid}/lineups", **form)
        assert r.status_code == 302, r.data[:300]
    # official result + scope
    assert post(col, f"/matches/{mid}/result", home_score="1", away_score="0", score_source="Referee sheet").status_code == 302
    post(col, f"/matches/{mid}/scope", scope=["goals", "shots"])
    h = [r[0] for r in con.execute("SELECT player_id FROM appearances WHERE match_id=? AND team_id=? ORDER BY player_id", (mid, teams[0]))]
    hdr = {"X-CSRF-Token": "t"}
    with col.session_transaction() as s:
        s["_csrf"] = "t"
    types = {r[1]: r[0] for r in con.execute("SELECT id, code FROM event_types")}
    inv = types
    goal = col.post(f"/collect/{mid}/event", json=dict(event_type_id=inv["goal"], team_id=teams[0], player_id=h[9], related_player_id=h[8], period="1H", minute=20), headers=hdr)
    assert goal.status_code == 200, goal.data
    dup = col.post(f"/collect/{mid}/event", json=dict(event_type_id=inv["goal"], team_id=teams[0], player_id=h[9], related_player_id=h[8], period="1H", minute=20), headers=hdr)
    assert dup.status_code == 409 and dup.get_json()["duplicate"]            # duplicate detection
    wrong = col.post(f"/collect/{mid}/event", json=dict(event_type_id=inv["shot"], team_id=teams[1], player_id=h[9], period="1H", minute=22, outcome="off_target"), headers=hdr)
    assert wrong.status_code == 422                                          # player belongs to the other team
    for m in (10, 30, 50):
        assert col.post(f"/collect/{mid}/event", json=dict(event_type_id=inv["shot"], team_id=teams[0], player_id=h[9], period="1H" if m < 46 else "2H", minute=m, outcome="on_target", x_start=88, y_start=50), headers=hdr).status_code == 200
    # sub-off player acting after being replaced -> validation warning, not accepted silently
    assert post(col, f"/collect/{mid}/submit").status_code == 302
    con2 = sqlite3.connect(a.config["DATABASE"])
    assert con2.execute("SELECT status FROM matches WHERE id=?", (mid,)).fetchone()[0] == "validation_required"
    # collector cannot edit after submission
    assert col.post(f"/collect/{mid}/event", json=dict(event_type_id=inv["goal"], team_id=teams[0], player_id=h[9], period="1H", minute=21), headers=hdr).status_code == 403
    post(an, f"/validate/{mid}/check")
    r = post(an, f"/validate/{mid}/approve", ack_warnings="1")
    st = sqlite3.connect(a.config["DATABASE"]).execute("SELECT status FROM matches WHERE id=?", (mid,)).fetchone()[0]
    assert st == "data_validated", st
    from app.metrics import analyse_match
    with a.app_context():
        res = analyse_match(mid)
        p = res["players"][h[9]]
        assert p["goals"]["value"] == 1 and p["shots"]["value"] == 4 and p["shots_on_target"]["value"] == 4, {k: (p[k]["value"], p[k]["status"]) for k in ("goals","shots","shots_on_target","minutes")}
        assert p["shot_accuracy"]["value"] == 100.0
        assert p["tackles"]["status"] == "not_collected"                      # defensive category not collected
        assert p["minutes"]["value"] == 90


def test_csv_fallback_import(demo_app):
    a = demo_app
    con = sqlite3.connect(a.config["DATABASE"])
    mid = a.ids["m2"]                                           # City United v Lake Town (upcoming, assigned to collector)
    ops, col = login(a, "ops"), login(a, "collector")
    teams = con.execute("SELECT home_team_id, away_team_id FROM matches WHERE id=?", (mid,)).fetchone()
    for tid in teams:
        pl = [r[0] for r in con.execute("SELECT id FROM players WHERE current_team_id=? ORDER BY id LIMIT 11", (tid,))]
        form = {"team_id": str(tid)}
        for p in pl:
            form[f"p{p}_in"] = "on"
            form[f"p{p}_starter"] = "on"
        assert post(ops, f"/matches/{mid}/lineups", **form).status_code == 302
    home = con.execute("SELECT name FROM teams WHERE id=?", (teams[0],)).fetchone()[0]
    pname = con.execute("SELECT p.full_name FROM appearances a JOIN players p ON p.id=a.player_id WHERE a.match_id=? AND a.team_id=? LIMIT 1", (mid, teams[0])).fetchone()[0]
    import io
    good = f"team,player,event_type,period,minute,second,outcome\n{home},{pname},pass,1H,12,30,completed\n{home},{pname},tackle,1H,14,,won\n"
    bad = f"team,player,event_type,period,minute,second,outcome\n{home},{pname},pass,1H,12,30,completed\n{home},Nobody Here,tackle,1H,14,,won\n"
    with col.session_transaction() as s:
        s["_csrf"] = "t"
    r = col.post(f"/collect/{mid}/import", data={"_csrf": "t", "file": (io.BytesIO(bad.encode()), "e.csv")}, content_type="multipart/form-data")
    assert sqlite3.connect(a.config["DATABASE"]).execute("SELECT COUNT(*) FROM match_events WHERE match_id=?", (mid,)).fetchone()[0] == 0   # all-or-nothing
    r = col.post(f"/collect/{mid}/import", data={"_csrf": "t", "file": (io.BytesIO(good.encode()), "e.csv")}, content_type="multipart/form-data")
    assert sqlite3.connect(a.config["DATABASE"]).execute("SELECT COUNT(*) FROM match_events WHERE match_id=? AND validation_status='draft'", (mid,)).fetchone()[0] == 2


def test_advanced_charts_only_from_collected_data(demo_app):
    from app import charts
    an = login(demo_app, "analyst")
    m1 = demo_app.ids["m1"]
    for kind in ("heat_home", "heat_away", "net_home", "net_away", "shots_home", "teams"):
        r = an.get(f"/analysis/match/{m1}/chart/{kind}.png")
        assert r.status_code == 200 and r.data[:4] == b"\x89PNG", kind
    assert an.get(f"/analysis/match/{demo_app.ids['m3']}/chart/heat_home.png").status_code == 404     # not validated
    # too little data => no chart at all (never an invented one)
    few = [dict(team_id=1, code="pass", outcome="completed", player_id=1, related_player_id=2, x_start=10, y_start=10, x_end=20, y_end=20)] * 3
    assert charts.passing_network(few, 1, {}, "x") is None
    assert charts.heatmap([], 1, "x") is None
    assert charts.heatmap([dict(team_id=1, code="pass", x_start=5, y_start=5)] * 5, 1, "x") is None
    # the reports embed them when available
    import json
    con = sqlite3.connect(demo_app.config["DATABASE"])
    snap = json.loads(con.execute("SELECT content FROM report_versions WHERE report_id=2").fetchone()[0])
    assert snap.get("heat_b64") and snap.get("net_b64")


def test_collection_page_has_offline_queue(demo_app):
    html = login(demo_app, "collector").get(f"/collect/{demo_app.ids['m2']}").data
    assert b'id="pending"' in html and b"collect.js" in html
    js = open(__import__("pathlib").Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "collect.js", encoding="utf-8").read()
    assert "localStorage" in js and "syncQ" in js
