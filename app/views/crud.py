"""Generic list / create / edit / delete / export screens for reference records, plus player profile and season teams."""
import csv
import io
import sqlite3

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import constants as C
from ..db import ex, q, scalar
from ..forms import F, form_value, parse_form
from ..security import audit, diff, has_perm, perm_required

bp = Blueprint("crud", __name__)

USERS_FK = ("users", "full_name", "user_type='employee' AND is_active=1")


def _players_after_save(rid, old, new):
    """Maintain player-team history whenever the current team changes."""
    new_team = new.get("current_team_id")
    old_team = old["current_team_id"] if old else None
    if new_team == old_team:
        return
    ex("UPDATE player_team_history SET end_date=date('now') WHERE player_id=? AND end_date IS NULL", (rid,))
    if new_team:
        ex("INSERT INTO player_team_history (player_id, team_id, start_date, shirt_number) VALUES (?,?,date('now'),?)",
           (rid, new_team, new.get("shirt_number")))


def _players_validate(vals, errs):
    if vals.get("date_of_birth") and not vals.get("dob_authorised"):
        errs["dob_authorised"] = "Date of birth can only be stored when its use is authorised - tick the box or clear the date."


ENTITIES = {
    "clubs": dict(
        table="clubs", title="Clubs", singular="Club", view=("football.view",), edit=("football.edit",),
        cols=["name", "country", "category", "verification_status"], search=["name", "country"], order="name",
        filter="verification_status",
        fields=[F("name", "Official club name", req=True), F("country", "Country or region"),
                F("category", "Club category", help="e.g. Premier League, academy, amateur"),
                F("verification_status", "Verification status", "select", options=C.VERIFICATION, req=True, default="unverified"),
                F("contact_details", "Contact details", "textarea"), F("notes", "Notes", "textarea")]),
    "teams": dict(
        table="teams", title="Teams", singular="Team", view=("football.view",), edit=("football.edit",),
        cols=["name", "club_id", "competition_category", "age_gender_category", "status"], search=["name"], order="name",
        filter="status",
        fields=[F("club_id", "Club", "fk", fk=("clubs", "name"), help="A club may have several teams."),
                F("name", "Team name", req=True), F("competition_category", "Competition category"),
                F("age_gender_category", "Age or gender category", help="Only where relevant and appropriate."),
                F("status", "Status", "select", options=["active", "inactive"], req=True, default="active"),
                F("notes", "Notes", "textarea")]),
    "players": dict(
        table="players", title="Players", singular="Player", view=("football.view",), edit=("football.edit",),
        cols=["full_name", "position", "current_team_id", "shirt_number", "verification_status"],
        search=["full_name", "position"], order="full_name", filter="verification_status",
        detail="crud.player_profile", after_save=_players_after_save, validate=_players_validate,
        export_exclude=["date_of_birth"],
        fields=[F("full_name", "Full name", req=True),
                F("position", "Playing position", "select", options=C.POSITIONS),
                F("current_team_id", "Current team", "fk", fk=("teams", "name")),
                F("shirt_number", "Shirt number", "int", help="Not permanent - team changes are kept in the history."),
                F("nationality", "Nationality"),
                F("preferred_foot", "Preferred foot", "select", options=["left", "right", "both"]),
                F("foot_verified", "Preferred foot verified", "bool"),
                F("date_of_birth", "Date of birth", "date", help="Store only when needed and authorised."),
                F("dob_authorised", "Use of date of birth is authorised", "bool"),
                F("verification_status", "Profile verification status", "select", options=C.VERIFICATION, req=True, default="unverified"),
                F("profile_source", "Source of profile information", help="Where was this information confirmed?"),
                F("date_last_verified", "Date last verified", "date"),
                F("image_permitted", "Profile image permitted", "bool"),
                F("notes", "Notes", "textarea")]),
    "competitions": dict(
        table="competitions", title="Competitions", singular="Competition", view=("football.view",), edit=("football.edit",),
        cols=["name", "organising_body", "category", "status"], search=["name"], order="name", filter="status",
        fields=[F("name", "Competition name", req=True), F("organising_body", "Organising body"),
                F("category", "Competition category"),
                F("status", "Status", "select", options=["active", "completed", "inactive"], req=True, default="active"),
                F("notes", "Notes", "textarea")]),
    "seasons": dict(
        table="seasons", title="Seasons", singular="Season", view=("football.view",), edit=("football.edit",),
        cols=["name", "competition_id", "start_date", "end_date", "status"], search=["name"], order="start_date DESC",
        filter="status", detail="crud.season_teams",
        fields=[F("competition_id", "Competition", "fk", fk=("competitions", "name"), req=True),
                F("name", "Season", req=True, help="e.g. 2026"), F("start_date", "Start date", "date"),
                F("end_date", "End date", "date"),
                F("status", "Status", "select", options=["active", "completed", "inactive"], req=True, default="active")]),
    "venues": dict(
        table="venues", title="Venues", singular="Venue", view=("football.view",), edit=("football.edit",),
        cols=["name", "region", "pitch_details"], search=["name", "region"], order="name",
        fields=[F("name", "Venue name", req=True), F("region", "Region"), F("pitch_details", "Pitch details", "textarea"),
                F("notes", "Notes", "textarea")]),
    "data_sources": dict(
        table="data_sources", title="Data sources and permissions", singular="Data source", view=("football.view",),
        edit=("football.edit",), cols=["name", "source_type", "permission_status", "url"], search=["name"], order="name",
        fields=[F("name", "Source name", req=True),
                F("source_type", "Source type", "select", req=True,
                  options=["live_collection", "video_review", "licensed_provider", "public_source", "client_supplied"]),
                F("permission_status", "Permission / licence status", "select", req=True,
                  options=["own_collection", "licensed", "permission_granted", "permission_pending", "no_permission"]),
                F("licence_notes", "Licence or permission notes", "textarea",
                  help="Publicly viewable data or footage is not automatically free to republish commercially."),
                F("url", "Reference link", "url")]),
    "services": dict(
        table="services", title="Service catalogue", singular="Service", view=("finance.view", "clients.view"),
        edit=("finance.manage",), cols=["name", "unit_price", "is_active"], search=["name"], order="name",
        fields=[F("name", "Service name", req=True), F("description", "Description", "textarea"),
                F("unit_price", "Standard price", "number", req=True, default=0), F("is_active", "Offered to clients", "bool", default=1)]),
    "clients": dict(
        table="clients", title="Clients", singular="Client", view=("clients.view",), edit=("clients.manage",),
        cols=["name", "client_type", "contact_person", "agreement_status", "next_followup"], search=["name", "contact_person"],
        order="name", filter="agreement_status", detail="business.client_detail", auto={},
        fields=[F("client_type", "Client type", "select", options=C.CLIENT_TYPES, req=True),
                F("name", "Organisation or individual name", req=True), F("contact_person", "Contact person"),
                F("email", "Email", "email"), F("phone", "Phone"),
                F("services_requested", "Services requested", "textarea"),
                F("agreement_status", "Agreement / proposal status", "select", options=C.AGREEMENT_STATUSES, req=True, default="prospect"),
                F("assigned_user_id", "Assigned company contact", "fk", fk=USERS_FK),
                F("next_followup", "Next follow-up date", "date"), F("notes", "Notes", "textarea"),
                F("is_active", "Active client", "bool", default=1)]),
    "leads": dict(
        table="leads", title="Prospects and leads", singular="Prospect", view=("marketing.manage",), edit=("marketing.manage",),
        cols=["name", "org_type", "status", "assigned_user_id", "next_followup"], search=["name", "contact_person"],
        order="next_followup", filter="status", detail="business.lead_detail",
        fields=[F("name", "Club, academy, player, agent or organisation", req=True),
                F("org_type", "Type", "select", options=C.CLIENT_TYPES), F("contact_person", "Contact person"),
                F("email", "Email", "email"), F("phone", "Phone"),
                F("status", "Lead status", "select", options=C.LEAD_STATUSES, req=True, default="new"),
                F("source", "How we found them"), F("assigned_user_id", "Assigned to", "fk", fk=USERS_FK),
                F("next_followup", "Next follow-up date", "date"), F("notes", "Notes", "textarea")]),
    "campaigns": dict(
        table="marketing_campaigns", title="Marketing campaigns", singular="Campaign", view=("marketing.manage",),
        edit=("marketing.manage",), cols=["name", "channel", "start_date", "end_date", "status"], search=["name"],
        order="start_date DESC", filter="status",
        fields=[F("name", "Campaign name", req=True), F("channel", "Channel", help="Social media, website, events..."),
                F("start_date", "Start date", "date"), F("end_date", "End date", "date"),
                F("budget", "Budget", "number"), F("link", "Website or social media link", "url"),
                F("status", "Status", "select", options=["planned", "running", "completed", "cancelled"], req=True, default="planned"),
                F("results", "Results", "textarea"), F("notes", "Notes", "textarea")]),
    "expenses": dict(
        table="expenses", title="Expense register", singular="Expense", view=("finance.view",), edit=("finance.manage",),
        cols=["expense_date", "category", "description", "amount", "receipt_ref"], search=["description", "payee", "category"],
        order="expense_date DESC", filter="category", auto={"recorded_by": "user"},
        fields=[F("expense_date", "Date", "date", req=True), F("category", "Category", "select", options=C.EXPENSE_CATEGORIES, req=True),
                F("description", "Description", req=True), F("amount", "Amount", "number", req=True, step="0.01"),
                F("payee", "Paid to"), F("receipt_ref", "Receipt reference", help="Receipt number or the file location of the scanned receipt."),
                F("related_match_id", "Related match", "fk", fk=("matches", "match_code")),
                F("related_client_id", "Related client", "fk", fk=("clients", "name"))]),
    "proposals": dict(
        table="proposals", title="Proposals and quotations", singular="Proposal", view=("finance.view",), edit=("finance.manage",),
        cols=["title", "client_id", "amount", "status", "valid_until"], search=["title"], order="created_at DESC",
        filter="status", auto={"created_by": "user"},
        fields=[F("title", "Title", req=True), F("client_id", "Client", "fk", fk=("clients", "name")),
                F("lead_id", "Prospect", "fk", fk=("leads", "name")), F("service_id", "Main service", "fk", fk=("services", "name")),
                F("amount", "Quoted amount", "number", req=True, step="0.01"),
                F("status", "Status", "select", options=["draft", "sent", "accepted", "rejected", "expired"], req=True, default="draft"),
                F("valid_until", "Valid until", "date"), F("notes", "Notes", "textarea")]),
}


def _entity(name):
    e = ENTITIES.get(name)
    if not e:
        abort(404)
    e["slug"] = name
    return e


def _need(e, kind):
    if not has_perm(*e[kind]):
        audit("access.denied", details={"path": request.path})
        abort(403)


def _fk_label_sql(f, alias="t"):
    table, label = f.fk[0], f.fk[1]
    return f"(SELECT {label} FROM {table} x WHERE x.id={alias}.{f.name}) AS {f.name}__lbl"


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client":
        abort(403)


@bp.route("/e/<name>/")
def list_view(name):
    e = _entity(name)
    _need(e, "view")
    fields = {f.name: f for f in e["fields"]}
    selects = ["t.*"] + [_fk_label_sql(fields[c]) for c in e["cols"] if c in fields and fields[c].type == "fk"]
    where, args = ["1=1"], []
    term = request.args.get("q", "").strip()
    if term and e.get("search"):
        where.append("(" + " OR ".join(f"t.{c} LIKE ?" for c in e["search"]) + ")")
        args += [f"%{term}%"] * len(e["search"])
    fv = request.args.get("filter", "")
    if fv and e.get("filter"):
        where.append(f"t.{e['filter']} = ?")
        args.append(fv)
    page = max(int(request.args.get("page", 1) or 1), 1)
    per = 50
    total = scalar(f"SELECT COUNT(*) FROM {e['table']} t WHERE {' AND '.join(where)}", args)
    rows = q(f"SELECT {', '.join(selects)} FROM {e['table']} t WHERE {' AND '.join(where)} ORDER BY {e['order']} LIMIT {per} OFFSET {(page-1)*per}", args)
    filter_opts = fields[e["filter"]].choices() if e.get("filter") and e["filter"] in fields else []
    return render_template("crud/list.html", e=e, rows=rows, fields=fields, total=total, page=page, per=per,
                           term=term, fv=fv, filter_opts=filter_opts,
                           can_edit=has_perm(*e["edit"]), can_export=has_perm("export.csv"))


def _save(e, rid=None):
    old = q(f"SELECT * FROM {e['table']} WHERE id=?", (rid,), one=True) if rid else None
    vals, errs = parse_form(e["fields"], request.form)
    if e.get("validate"):
        e["validate"](vals, errs)
    if errs:
        return None, vals, errs, old
    names = list(vals.keys())
    if rid:
        sets = ", ".join(f"{n}=?" for n in names)
        ex(f"UPDATE {e['table']} SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?" if "updated_at" in _cols(e) else
           f"UPDATE {e['table']} SET {sets} WHERE id=?", [vals[n] for n in names] + [rid])
        audit(f"{e['table']}.update", e["table"], rid, diff(old, vals, names))
    else:
        for col, who in (e.get("auto") or {}).items():
            if who == "user":
                vals[col] = g.user["id"]
                names.append(col)
        rid = ex(f"INSERT INTO {e['table']} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})", [vals[n] for n in names])
        audit(f"{e['table']}.create", e["table"], rid, {k: v for k, v in vals.items() if v not in (None, "")})
    if e.get("after_save"):
        e["after_save"](rid, old, vals)
    return rid, vals, errs, old


def _cols(e):
    return {r["name"] for r in q(f"PRAGMA table_info({e['table']})")}


@bp.route("/e/<name>/new", methods=["GET", "POST"])
def create(name):
    e = _entity(name)
    _need(e, "edit")
    if request.method == "POST":
        rid, vals, errs, _ = _save(e)
        if not errs:
            flash(f"{e['singular']} saved.", "ok")
            return redirect(url_for("crud.list_view", name=name))
        flash("Some details need attention - see the highlighted fields.", "error")
        return render_template("crud/form.html", e=e, row=None, form=request.form, errs=errs), 422
    return render_template("crud/form.html", e=e, row=None, form=None, errs={})


@bp.route("/e/<name>/<int:rid>/edit", methods=["GET", "POST"])
def edit(name, rid):
    e = _entity(name)
    _need(e, "edit")
    row = q(f"SELECT * FROM {e['table']} WHERE id=?", (rid,), one=True)
    if not row:
        abort(404)
    if request.method == "POST":
        _, vals, errs, _old = _save(e, rid)
        if not errs:
            flash(f"{e['singular']} updated.", "ok")
            return redirect(url_for("crud.list_view", name=name))
        flash("Some details need attention - see the highlighted fields.", "error")
        return render_template("crud/form.html", e=e, row=row, form=request.form, errs=errs), 422
    return render_template("crud/form.html", e=e, row=row, form=None, errs={})


@bp.route("/e/<name>/<int:rid>/delete", methods=["POST"])
def delete(name, rid):
    e = _entity(name)
    _need(e, "edit")
    row = q(f"SELECT * FROM {e['table']} WHERE id=?", (rid,), one=True)
    if not row:
        abort(404)
    try:
        ex(f"DELETE FROM {e['table']} WHERE id=?", (rid,))
        audit(f"{e['table']}.delete", e["table"], rid, dict(row))
        flash(f"{e['singular']} deleted.", "ok")
    except sqlite3.IntegrityError:
        g.db.rollback()
        flash(f"This {e['singular'].lower()} is used by other records and cannot be deleted. Mark it inactive instead.", "error")
    return redirect(url_for("crud.list_view", name=name))


def _csv_safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


@bp.route("/e/<name>/export.csv")
@perm_required("export.csv")
def export(name):
    e = _entity(name)
    _need(e, "view")
    rows = q(f"SELECT * FROM {e['table']} ORDER BY id")
    out = io.StringIO()
    w = csv.writer(out)
    if rows:
        cols = [c for c in rows[0].keys() if c not in e.get("export_exclude", [])]
        w.writerow(cols)
        for r in rows:
            w.writerow([_csv_safe(r[c]) for c in cols])
    audit("export.csv", e["table"], None, {"rows": len(rows)})
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={e['table']}.csv"})


# ----------------------------------------------------------------------------- player profile
@bp.route("/players/<int:pid>")
@perm_required("football.view")
def player_profile(pid):
    p = q("SELECT p.*, t.name AS team_name FROM players p LEFT JOIN teams t ON t.id=p.current_team_id WHERE p.id=?", (pid,), one=True)
    if not p:
        abort(404)
    history = q("SELECT h.*, t.name AS team_name FROM player_team_history h JOIN teams t ON t.id=h.team_id "
                "WHERE h.player_id=? ORDER BY COALESCE(h.start_date,'0000') DESC", (pid,))
    matches = q("SELECT m.id, m.match_code, m.kickoff, m.status, ht.name AS home, at.name AS away, a.role, a.appearance_status "
                "FROM appearances a JOIN matches m ON m.id=a.match_id JOIN teams ht ON ht.id=m.home_team_id "
                "JOIN teams at ON at.id=m.away_team_id WHERE a.player_id=? ORDER BY m.kickoff DESC", (pid,))
    show_dob = bool(p["dob_authorised"] and p["date_of_birth"])
    return render_template("crud/player_profile.html", p=p, history=history, matches=matches, show_dob=show_dob,
                           can_edit=has_perm("football.edit"))


@bp.route("/seasons/<int:sid>/teams", methods=["GET", "POST"])
@perm_required("football.view")
def season_teams(sid):
    s = q("SELECT s.*, c.name AS comp FROM seasons s JOIN competitions c ON c.id=s.competition_id WHERE s.id=?", (sid,), one=True)
    if not s:
        abort(404)
    if request.method == "POST":
        if not has_perm("football.edit"):
            abort(403)
        chosen = {int(x) for x in request.form.getlist("team") if x.isdigit()}
        ex("DELETE FROM competition_teams WHERE season_id=?", (sid,))
        for t in chosen:
            if scalar("SELECT COUNT(*) FROM teams WHERE id=?", (t,)):
                ex("INSERT INTO competition_teams (season_id, team_id) VALUES (?,?)", (sid, t))
        audit("season.teams", "seasons", sid, {"teams": sorted(chosen)})
        flash("Participating teams saved.", "ok")
        return redirect(url_for("crud.season_teams", sid=sid))
    teams = q("SELECT t.id, t.name, c.name AS club FROM teams t LEFT JOIN clubs c ON c.id=t.club_id ORDER BY t.name")
    chosen = {r["team_id"] for r in q("SELECT team_id FROM competition_teams WHERE season_id=?", (sid,))}
    return render_template("crud/season_teams.html", s=s, teams=teams, chosen=chosen, can_edit=has_perm("football.edit"))
