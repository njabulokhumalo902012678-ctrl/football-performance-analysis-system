"""Fictional demonstration data. NEVER contains real clients or players.
Creates users for all roles, clubs, players, matches (validated / awaiting validation / delayed / upcoming),
finance records, and runs a real report workflow through the application so the demo reflects actual behaviour."""
import random
import re
import sqlite3
from datetime import datetime, timedelta

from .security import hash_password

DEMO_PASSWORD = "Demo#2026pass"

USERS = [
    ("md", "Thandi Dlamini", "md@example.test", ["managing_director"]),
    ("ops", "Sipho Nkosi", "ops@example.test", ["operations_manager"]),
    ("analyst", "Lindiwe Mamba", "analyst@example.test", ["football_analyst"]),
    ("scout", "Bheki Simelane", "scout@example.test", ["video_scouting_analyst"]),
    ("tech", "Mandla Shongwe", "tech@example.test", ["technology_lead"]),
    ("finance", "Nomsa Gama", "finance@example.test", ["finance_marketing_lead"]),
    ("collector", "Sibusiso Magagula", "collector@example.test", ["data_collector"]),
]

RUDI = [("Mandla Dlamini", "Goalkeeper", 1), ("Sifiso Mthembu", "Right Back", 2), ("Bongani Dlamini", "Centre Back", 3),
        ("Thabo Nkambule", "Centre Back", 4), ("Musa Gama", "Left Back", 5), ("Kwanele Mthembu", "Defensive Midfielder", 6),
        ("Phila Cele", "Central Midfielder", 8), ("Lucky Mabuza", "Attacking Midfielder", 10), ("Themba Ndlovu", "Right Winger", 7),
        ("Siza Mahlangu", "Striker", 9), ("Njabulo Fakudze", "Left Winger", 11),
        ("Lwazi Shabalala", "Central Midfielder", 14), ("Mpho Zwane", "Striker", 15), ("Dumisani Vilakati", "Goalkeeper", 12)]
CITY = [("Vusi Mamba", "Goalkeeper", 1), ("Teboho Maseko", "Right Back", 2), ("Sandile Hlophe", "Centre Back", 4),
        ("Jabulani Simelane", "Centre Back", 5), ("Zweli Dube", "Left Back", 3), ("Kenny Motsa", "Defensive Midfielder", 6),
        ("Tsepo Nxumalo", "Central Midfielder", 8), ("Bheki Mavuso", "Attacking Midfielder", 10), ("Mthunzi Sukati", "Right Winger", 7),
        ("Alex Tfwala", "Striker", 9), ("Fana Matsebula", "Left Winger", 11),
        ("Joel Makhanya", "Striker", 14), ("Dan Khumalo", "Central Midfielder", 15), ("Rob Nsibande", "Goalkeeper", 12)]
LAKE = [(f"Lake Player {i}", pos, i) for i, pos in enumerate(
    ["Goalkeeper", "Right Back", "Centre Back", "Centre Back", "Left Back", "Defensive Midfielder", "Central Midfielder",
     "Attacking Midfielder", "Right Winger", "Striker", "Left Winger"], start=1)]


def _ts(d):
    return d.strftime("%Y-%m-%d %H:%M:%S")


def build(db_path, app=None):
    """Populate a freshly initialised database. Returns summary dict."""
    random.seed(2026)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    def ins(sql, args=()):
        cur.execute(sql, args)
        return cur.lastrowid

    pw = hash_password(DEMO_PASSWORD)
    uid = {}
    for username, name, email, roles in USERS:
        uid[username] = ins("INSERT INTO users (username,email,full_name,password_hash,user_type,must_change_password) VALUES (?,?,?,?, 'employee',0)", (username, email, name, pw))
        for r in roles:
            cur.execute("INSERT INTO user_roles SELECT ?, id FROM roles WHERE code=?", (uid[username], r))

    # --- football records
    clubs = {n: ins("INSERT INTO clubs (name,country,category,verification_status) VALUES (?,?,?,?)", (n, "Eswatini (fictional)", "Demo club", "verified"))
             for n in ("Rudimentary FC", "City United FC", "Lake Town FC")}
    teams = {n: ins("INSERT INTO teams (club_id,name,competition_category,status) VALUES (?,?, 'Senior men','active')", (cid, n)) for n, cid in clubs.items()}
    comp = ins("INSERT INTO competitions (name,organising_body,category,status) VALUES ('Demo Premier League','Fictional League Association','Senior men','active')")
    season = ins("INSERT INTO seasons (competition_id,name,start_date,end_date,status) VALUES (?, '2026','2026-02-01','2026-11-30','active')", (comp,))
    for t in teams.values():
        cur.execute("INSERT INTO competition_teams VALUES (?,?)", (season, t))
    v1 = ins("INSERT INTO venues (name,region,pitch_details) VALUES ('Rudimentary Stadium','Hhohho','Natural grass, floodlit')")
    v2 = ins("INSERT INTO venues (name,region,pitch_details) VALUES ('Lake Town Ground','Manzini','Artificial turf')")
    v3 = ins("INSERT INTO venues (name,region) VALUES ('City United Park','Manzini')")

    players = {}
    for club, roster in (("Rudimentary FC", RUDI), ("City United FC", CITY), ("Lake Town FC", LAKE)):
        for name, pos, shirt in roster:
            pid = ins("INSERT INTO players (full_name,position,current_team_id,shirt_number,nationality,verification_status,profile_source,date_last_verified) "
                      "VALUES (?,?,?,?,?,?,?,?)", (name, pos, teams[club], shirt, "Eswatini", "verified", "Fictional demo data", "2026-09-01"))
            cur.execute("INSERT INTO player_team_history (player_id,team_id,start_date,shirt_number) VALUES (?,?,?,?)", (pid, teams[club], "2026-02-01", shirt))
            players[name] = pid

    # --- clients, services, commercial
    c_rud = ins("INSERT INTO clients (client_type,name,contact_person,email,phone,services_requested,agreement_status,assigned_user_id,notes) VALUES (?,?,?,?,?,?,?,?,?)",
                ("Football club", "Rudimentary FC", "Coach Joseph Dlamini", "coach@rudimentary.example.test", "+268 7600 0001",
                 "Player performance reports and match analysis for the 2026 season", "active", uid["finance"], "Demo client"))
    c_city = ins("INSERT INTO clients (client_type,name,contact_person,email,phone,services_requested,agreement_status,assigned_user_id) VALUES (?,?,?,?,?,?,?,?)",
                 ("Football club", "City United FC", "Ms Zanele Motsa", "analysis@cityunited.example.test", "+268 7600 0002", "Match analysis reports", "agreed", uid["finance"]))
    for username, name, email, cid in (("client.rudimentary", "Joseph Dlamini", "coach@rudimentary.example.test", c_rud),
                                       ("client.city", "Zanele Motsa", "analysis@cityunited.example.test", c_city)):
        u = ins("INSERT INTO users (username,email,full_name,password_hash,user_type,must_change_password) VALUES (?,?,?,?, 'client',0)", (username, email, name, pw))
        cur.execute("INSERT INTO user_roles SELECT ?, id FROM roles WHERE code='client'", (u,))
        cur.execute("INSERT INTO client_users (client_id,user_id) VALUES (?,?)", (cid, u))
    svc = {n: ins("INSERT INTO services (name,description,unit_price) VALUES (?,?,?)", (n, d, p)) for n, d, p in [
        ("Player performance report", "Single-match report for one player", 450), ("Match analysis report", "Full match and team analysis", 1200),
        ("Scouting report", "Scouting assessment with video evidence", 650), ("Season analysis package", "10 match reports + 20 player reports", 8500)]}
    today = datetime.now().date()
    inv1 = ins("INSERT INTO invoices (invoice_number,client_id,issue_date,due_date,status,subtotal,tax_rate,tax_amount,total,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (f"INV-{today.year}-0001", c_rud, str(today - timedelta(days=20)), str(today + timedelta(days=10)), "partial", 1650, 0, 0, 1650, uid["finance"]))
    cur.execute("INSERT INTO invoice_items (invoice_id,service_id,description,quantity,unit_price,line_total) VALUES (?,?,?,?,?,?)", (inv1, svc["Match analysis report"], "Match analysis - September", 1, 1200, 1200))
    cur.execute("INSERT INTO invoice_items (invoice_id,service_id,description,quantity,unit_price,line_total) VALUES (?,?,?,?,?,?)", (inv1, svc["Player performance report"], "Player reports", 1, 450, 450))
    cur.execute("INSERT INTO payments (invoice_id,paid_date,amount,method,reference,recorded_by) VALUES (?,?,?,?,?,?)", (inv1, str(today - timedelta(days=5)), 800, "Bank transfer", "REF-1001", uid["finance"]))
    inv2 = ins("INSERT INTO invoices (invoice_number,client_id,issue_date,due_date,status,subtotal,tax_rate,tax_amount,total,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (f"INV-{today.year}-0002", c_city, str(today - timedelta(days=45)), str(today - timedelta(days=15)), "sent", 1200, 0, 0, 1200, uid["finance"]))
    cur.execute("INSERT INTO invoice_items (invoice_id,service_id,description,quantity,unit_price,line_total) VALUES (?,?,?,?,?,?)", (inv2, svc["Match analysis report"], "Match analysis - August", 1, 1200, 1200))
    for d, cat, desc, amt in [(today - timedelta(days=12), "Transport", "Fuel to Lake Town Ground", 380), (today - timedelta(days=30), "Software and hosting", "Server hosting - quarter", 900),
                              (today - timedelta(days=8), "Equipment", "Tablet stand and power bank", 520)]:
        cur.execute("INSERT INTO expenses (expense_date,category,description,amount,receipt_ref,recorded_by) VALUES (?,?,?,?,?,?)", (str(d), cat, desc, amt, "Receipt on file (demo)", uid["finance"]))
    for n, t, s in [("Hhohho Youth Academy", "Academy", "contacted"), ("Agent: M. Gamedze (fictional)", "Agent", "meeting_booked"), ("Eagles FC", "Football club", "new")]:
        cur.execute("INSERT INTO leads (name,org_type,status,source,assigned_user_id,next_followup) VALUES (?,?,?,?,?,?)", (n, t, s, "Referral", uid["finance"], str(today + timedelta(days=3))))
    cur.execute("INSERT INTO marketing_campaigns (name,channel,start_date,status,notes) VALUES ('Season launch','Social media',?, 'running','Demo campaign')", (str(today - timedelta(days=14)),))
    ins("INSERT INTO proposals (client_id,title,service_id,amount,status,created_by) VALUES (?,?,?,?,?,?)", (c_city, "Season analysis package 2026", svc["Season analysis package"], 8500, "sent", uid["finance"]))

    # --- matches
    def mk(code, home, away, ko, venue, status, deadline=None, client=None, score=None, source=None):
        h, a = (score or (None, None))
        mid = ins("INSERT INTO matches (match_code,competition_id,season_id,home_team_id,away_team_id,kickoff,venue_id,status,home_score,away_score,score_source,attendance,collection_deadline,client_id,created_by) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (code, comp, season, teams[home], teams[away], ko, venue, status, h, a, source, 1250 if score else None, deadline, client, uid["ops"]))
        cur.execute("INSERT INTO match_status_history (match_id,new_status,user_id,note) VALUES (?,?,?,?)", (mid, "scheduled", uid["ops"], "Fixture created"))
        for item in ["Collector confirmed attendance", "Backup collector arranged", "Lineups received from both teams", "Collection device charged and tested", "Transport and access to venue arranged"]:
            cur.execute("INSERT INTO match_checklist_items (match_id,label,done) VALUES (?,?,?)", (mid, item, 1 if score else 0))
        return mid

    m1 = mk("M-2026-0001", "Rudimentary FC", "City United FC", "2026-10-04 15:00:00", v1, "validation_required", "2026-10-05 18:00:00", c_rud, (2, 1), "Referee match sheet")
    m3 = mk("M-2026-0003", "Rudimentary FC", "Lake Town FC", "2026-10-10 15:00:00", v1, "validation_required", "2026-10-11 18:00:00", c_rud, (1, 0), "Referee match sheet")
    m4 = mk("M-2026-0004", "Lake Town FC", "City United FC", "2026-10-11 15:00:00", v2, "assigned", "2026-10-11 20:00:00", c_city)
    m2 = mk("M-2026-0002", "City United FC", "Lake Town FC", (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d 15:00:00"), v3, "assigned",
            (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d 18:00:00"), c_city)
    m5 = mk("M-2026-0005", "Rudimentary FC", "City United FC", (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d 15:00:00"), v1, "scheduled", None, c_rud)
    for mid, role in ((m4, "collector"), (m2, "collector"), (m3, "collector"), (m1, "collector")):
        cur.execute("INSERT INTO collection_assignments (match_id,user_id,assignment_role,deadline,status) VALUES (?,?,?,?, 'submitted')" if mid in (m1, m3) else
                    "INSERT INTO collection_assignments (match_id,user_id,assignment_role,deadline) VALUES (?,?,?,?)", (mid, uid["collector"], role, None))
    for mid in (m1, m3):
        cur.execute("INSERT INTO collection_assignments (match_id,user_id,assignment_role) VALUES (?,?, 'analyst')", (mid, uid["analyst"]))

    ev_id = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM event_types")}

    def squad(mid, team, roster, starters, subs_info):
        """starters: first 11. subs_info: {name: dict(on=, off=, status=)} for the rest + off-minutes for starters."""
        for i, (name, pos, shirt) in enumerate(roster):
            pid = players[name]
            info = subs_info.get(name, {})
            starter = i < 11
            if not starter and not info:
                status, on = "unused_substitute", None
            else:
                status, on = "played", info.get("on")
            cur.execute("INSERT INTO match_squads (match_id,team_id,player_id,shirt_number,is_starter,position) VALUES (?,?,?,?,?,?)", (mid, teams[team], pid, shirt, 1 if starter else 0, pos))
            cur.execute("INSERT INTO appearances (match_id,team_id,player_id,role,start_position,sub_on_minute,sub_off_minute,dismissed_minute,appearance_status,source_id,verification_status) VALUES (?,?,?,?,?,?,?,?,?,1,?)",
                        (mid, teams[team], pid, "starter" if starter else "substitute", pos, on, info.get("off"), info.get("red"), status, "unverified"))

    rudi_subs = {"Kwanele Mthembu": {"off": 63}, "Lwazi Shabalala": {"on": 63}}
    city_subs = {"Alex Tfwala": {"off": 88}, "Joel Makhanya": {"on": 88}}
    squad(m1, "Rudimentary FC", RUDI, 11, rudi_subs)
    squad(m1, "City United FC", CITY, 11, city_subs)
    squad(m3, "Rudimentary FC", RUDI, 11, {})
    squad(m3, "Lake Town FC", LAKE, 11, {})

    def E(mid, team, code, player, minute, outcome=None, related=None, sp=None, xy=None, status="validated", second=None, xy_end=None):
        pid = players[player] if player else None
        rel = players[related] if related else None
        period = "1H" if minute <= 45 else "2H"
        x, y = xy if xy else (None, None)
        xe, ye = xy_end if xy_end else (None, None)
        cur.execute("INSERT INTO match_events (match_id,team_id,player_id,event_type_id,period,minute,second,outcome,related_player_id,x_start,y_start,x_end,y_end,set_piece_type,collector_id,source_id,validation_status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)", (mid, teams[team], pid, ev_id[code], period, minute, second, outcome, rel, x, y, xe, ye, sp, uid["collector"], status))

    def pool(roster, subs, minute, outfield=True):
        out = []
        for i, (name, pos, _s) in enumerate(roster):
            info = subs.get(name, {})
            start = 0 if i < 11 else info.get("on")
            if start is None:
                continue
            end = info.get("off", 90)
            if start <= minute < end and not (outfield and pos == "Goalkeeper"):
                out.append((name, pos))
        return out

    def bulk(mid, team, roster, subs, spec, status="validated"):
        for code, n, outcomes in spec:
            for _ in range(n):
                minute = random.randint(1, 89)
                p = pool(roster, subs, minute)
                if code in ("clearance", "block", "interception"):
                    p = [x for x in p if "Back" in x[1] or "Centre" in x[1] or "Defensive" in x[1]] or p
                if code in ("shot",):
                    p = [x for x in p if x[1] in ("Striker", "Right Winger", "Left Winger", "Attacking Midfielder", "Central Midfielder")] or p
                name = random.choice(p)[0]
                outcome = random.choice(outcomes) if outcomes else None
                xy = None
                if code == "shot":
                    xy = (random.uniform(72, 96), random.uniform(25, 75))
                elif code in ("pass", "cross", "tackle", "interception", "clearance", "block", "recovery", "duel", "key_pass", "corner", "free_kick", "foul"):
                    xy = (random.uniform(5, 95), random.uniform(5, 95))
                if code == "corner":
                    xy = (99, random.choice([2, 98]))
                rel, xe = None, None
                if code == "pass":
                    mates = [x[0] for x in p if x[0] != name]
                    rel = random.choice(mates) if mates else None
                    xe = (min(100, max(0, xy[0] + random.uniform(-10, 25))), random.uniform(5, 95))
                E(mid, team, code, name, minute, outcome, related=rel, xy=xy, xy_end=xe, status=status, sp="corner" if code == "corner" else None, second=random.randint(0, 59))

    # match 1 ------------------------------------------------------------
    R, C_ = "Rudimentary FC", "City United FC"
    E(m1, R, "goal", "Siza Mahlangu", 12, related="Themba Ndlovu", xy=(91, 48))
    E(m1, C_, "goal", "Alex Tfwala", 41, related="Fana Matsebula", xy=(88, 55))
    E(m1, R, "goal", "Njabulo Fakudze", 71, related="Lwazi Shabalala", xy=(86, 30), sp="corner")
    E(m1, C_, "card", "Teboho Maseko", 28, "yellow")
    E(m1, R, "card", "Bongani Dlamini", 76, "yellow")
    E(m1, R, "substitution", "Kwanele Mthembu", 63, related="Lwazi Shabalala")
    E(m1, C_, "substitution", "Alex Tfwala", 88, related="Joel Makhanya")
    bulk(m1, R, RUDI, rudi_subs, [("pass", 150, ["completed"] * 5 + ["incomplete"]), ("key_pass", 7, [None]), ("cross", 12, ["completed", "incomplete", "incomplete"]),
                                  ("shot", 7, ["on_target", "on_target", "off_target", "off_target", "blocked"]), ("corner", 6, [None]), ("foul", 9, ["committed"]),
                                  ("tackle", 18, ["won", "won", "lost"]), ("interception", 10, [None]), ("clearance", 12, [None]), ("block", 4, [None]), ("recovery", 28, [None]),
                                  ("duel", 22, ["won", "lost"]), ("aerial_duel", 10, ["won", "lost"]), ("free_kick", 5, [None])])
    bulk(m1, C_, CITY, city_subs, [("pass", 115, ["completed"] * 3 + ["incomplete"]), ("key_pass", 4, [None]), ("cross", 8, ["completed", "incomplete", "incomplete"]),
                                   ("shot", 5, ["on_target", "off_target", "off_target", "blocked"]), ("corner", 3, [None]), ("foul", 14, ["committed"]),
                                   ("tackle", 20, ["won", "lost"]), ("interception", 8, [None]), ("clearance", 17, [None]), ("block", 5, [None]), ("recovery", 24, [None]),
                                   ("duel", 20, ["won", "lost"]), ("aerial_duel", 12, ["won", "lost"]), ("free_kick", 7, [None])])
    for cat in ("goals", "shots", "passes", "defensive", "discipline", "set_pieces"):
        cur.execute("INSERT INTO match_collection_scope VALUES (?,?,1)", (m1, cat))
    cur.execute("UPDATE appearances SET dismissed_minute=NULL WHERE match_id=?", (m1,))
    # match 1 is submitted data awaiting validation -> status 'submitted'; the demo workflow validates it through the app
    cur.execute("UPDATE match_events SET validation_status='submitted' WHERE match_id=?", (m1,))

    # match 3 (awaiting validation with deliberate problems) ---------------
    E(m3, R, "goal", "Siza Mahlangu", 15, related="Themba Ndlovu", status="submitted")
    E(m3, R, "goal", "Siza Mahlangu", 15, related="Themba Ndlovu", status="submitted")      # duplicate -> also score mismatch (2 recorded vs 1 official)
    E(m3, R, "shot", "Njabulo Fakudze", 33, "on_target", xy=(85, 40), status="submitted")
    E(m3, "Lake Town FC", "shot", "Lake Player 10", 58, "off_target", xy=(80, 60), status="submitted")
    E(m3, R, "card", "Phila Cele", 80, "red", status="submitted")
    for cat in ("goals", "shots", "discipline"):
        cur.execute("INSERT INTO match_collection_scope VALUES (?,?,1)", (m3, cat))
    cur.execute("INSERT INTO match_status_history (match_id,old_status,new_status,user_id,note) VALUES (?,?,?,?,?)", (m3, "collection_in_progress", "validation_required", uid["collector"], "Awaiting validation"))
    cur.execute("INSERT INTO match_status_history (match_id,old_status,new_status,user_id,note) VALUES (?,?,?,?,?)", (m1, "collection_in_progress", "validation_required", uid["collector"], "Awaiting validation"))

    # video, scouting, tasks ----------------------------------------------
    vid = ins("INSERT INTO video_assets (title,match_id,reference,permission_status,licence_notes,access_restriction,uploaded_by) VALUES (?,?,?,?,?,?,?)",
              ("Rudimentary v City United - full match (demo)", m1, "https://example.test/demo-video", "permitted", "Filmed by company staff with club permission (demo).", "client_shareable", uid["scout"]))
    cur.execute("INSERT INTO video_clips (video_id,match_id,player_id,start_seconds,end_seconds,event_category,tags,notes,created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                (vid, m1, players["Siza Mahlangu"], 720, 735, "goal", "opener,finishing", "Finish after run behind the line.", uid["scout"]))
    ins("INSERT INTO video_assets (title,match_id,reference,permission_status,licence_notes,access_restriction,uploaded_by) VALUES (?,?,?,?,?,?,?)",
        ("Lake Town FC highlights (permission pending)", m3, "https://example.test/pending", "pending", "Permission request sent.", "internal_only", uid["scout"]))
    sc = ins("INSERT INTO scouting_reports (player_id,position_role,observation_date,factual_evidence,technical_strengths,tactical_strengths,development_areas,decision_making,video_refs,confidence,recommendation,analyst_id,review_status) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (players["Siza Mahlangu"], "Striker", "2026-10-04",
                                                       "Scored the opening goal on 12 minutes. Recorded 90 minutes. See clip at 720s.", "Clean finishing with either side.", "Good movement between centre-backs.",
                                                       "Link-up play when dropping deep.", "Chose the right option on the opening goal.", "Clip: opener (720s)", "low",
                                                       "Continue monitoring; one match is not enough for a firm conclusion.", uid["scout"], "submitted"))
    cur.execute("INSERT INTO scouting_report_matches VALUES (?,?)", (sc, m1))
    for title, who, dept, prio, due, rel in [("Confirm lineups for M-2026-0002", "ops", "Operations", "high", str(today + timedelta(days=2)), m2),
                                             ("Validate M-2026-0001 data", "analyst", "Analysis", "high", str(today - timedelta(days=1)), m1),
                                             ("Check database backup restore", "tech", "Technology", "normal", str(today + timedelta(days=5)), None),
                                             ("Follow up City United invoice", "finance", "Finance and Marketing", "urgent", str(today - timedelta(days=2)), None),
                                             ("Review video permissions", "scout", "Scouting", "normal", str(today + timedelta(days=7)), None)]:
        cur.execute("INSERT INTO tasks (title,assigned_to,department,priority,due_date,related_type,related_id,created_by) VALUES (?,?,?,?,?,?,?,?)",
                    (title, uid[who], dept, prio, due, "match" if rel else None, rel, uid["md"]))
    con.commit()
    ids = dict(m1=m1, m2=m2, m3=m3, m4=m4, m5=m5, players=players, clients=dict(rud=c_rud, city=c_city), scouting=sc)
    con.close()
    return ids


def run_workflow(app, ids):
    """Drive the real application (as each employee) through validation, analysis, report creation, approval and delivery."""
    out = {}

    def login(client, user):
        client.get("/login")
        with client.session_transaction() as s:
            s["_csrf"] = "demo-token"
        r = client.post("/login", data={"identifier": user, "password": DEMO_PASSWORD, "_csrf": "demo-token"})
        assert r.status_code == 302, f"login {user} failed"

    def post(client, url, **data):
        with client.session_transaction() as s:
            s["_csrf"] = "demo-token"
        data["_csrf"] = "demo-token"
        r = client.post(url, data=data, follow_redirects=False)
        assert r.status_code in (200, 302), f"{url} -> {r.status_code}"
        return r

    pid = ids["players"]
    # analyst validates match 1: run checks, then approve
    an = app.test_client()
    login(an, "analyst")
    post(an, f"/validate/{ids['m1']}/check")
    r = post(an, f"/validate/{ids['m1']}/approve", ack_warnings="1")
    post(an, f"/validate/{ids['m3']}/check")
    post(an, f"/analysis/match/{ids['m1']}/run", note="Initial run")
    post(an, f"/analysis/match/{ids['m1']}/note", note_type="observation", body="Rudimentary FC used the wide areas effectively in the first half.")
    post(an, f"/analysis/match/{ids['m1']}/note", note_type="fact", body="Substitution at 63': Lwazi Shabalala on for Kwanele Mthembu.")
    # player report
    post(an, "/reports/new", type="player", pair=f"{ids['m1']}:{pid['Siza Mahlangu']}", client_id=str(ids["clients"]["rud"]))
    post(an, "/reports/1/save", observations="Opened the scoring with a well-timed run in behind.\nHeld the ball up well under pressure.",
         strengths="Movement in the box\nFinishing", development="Link-up play when dropping deep\nPressing triggers",
         training="Finishing from different angles\nReceiving under pressure", next_match="Stay central to occupy both centre-backs\nWork on first touch against a high press",
         rating="7.5", rating_justification="Scored the opener, 90 minutes, good movement; limited involvement in build-up (rubric level 7-8).", client_id=str(ids["clients"]["rud"]))
    post(an, "/reports/1/submit")
    # match report
    post(an, "/reports/new", type="match", match_id=str(ids["m1"]), client_id=str(ids["clients"]["rud"]))
    post(an, "/reports/2/save", insights="Rudimentary created more shots (9 v 6).\nBoth sides committed a high number of fouls.",
         tactical="Rudimentary stretched the pitch with wide players.\nCity United were most dangerous on the break.",
         strengths="Chance creation\nWork rate in midfield", weaknesses="Concentration after scoring\nToo many fouls in midfield",
         training="Defending transitions\nSet-piece organisation", next_match="Keep width but protect the space behind full-backs",
         incidents="Corner on 71' led to the winning goal.", client_id=str(ids["clients"]["rud"]))
    post(an, "/reports/2/submit")
    # team report for the client (focus: Rudimentary only)
    post(an, "/reports/new", type="team", match_id=str(ids["m1"]), team_id="1", client_id=str(ids["clients"]["rud"]))
    # scouting report by scout
    sc = app.test_client()
    login(sc, "scout")
    post(sc, "/reports/new", type="scouting", scouting_id=str(ids["scouting"]), client_id=str(ids["clients"]["rud"]))
    # MD approves reports 1 and 2; leaves scouting report for later
    md = app.test_client()
    login(md, "md")
    post(md, "/reports/1/approve")
    post(md, "/reports/2/approve")
    post(md, f"/scouting/{ids['scouting']}/status", status="approved")
    # finance shares
    fin = app.test_client()
    login(fin, "finance")
    post(fin, "/reports/1/share", client_id=str(ids["clients"]["rud"]))
    post(fin, "/reports/2/share", client_id=str(ids["clients"]["rud"]))
    # scouting report: draft -> submitted so the MD has something to approve
    post(sc, "/reports/4/submit")
    return out
