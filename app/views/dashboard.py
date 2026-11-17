"""Role-specific dashboards. Each indicator links to the relevant list and is shown only if the user may see it."""
import re

from flask import Blueprint, g, redirect, render_template, url_for

from .. import constants as C
from ..db import get_setting, local_now, local_now_str, q, scalar
from ..security import has_perm, login_required, primary_role

bp = Blueprint("dashboard", __name__)

# Match groups used by the dashboard links and the match list filter.
PRE = "('scheduled','assigned','ready_for_collection','collection_in_progress','corrections_required')"
GROUPS = {
    "scheduled": ("Scheduled", "status IN ('scheduled','assigned','ready_for_collection')"),
    "completed": ("Completed", "status IN ('data_validated','analysis_in_progress','report_under_review','approved','delivered_to_client','archived')"),
    "awaiting_collection": ("Awaiting data collection", f"status IN {PRE} AND kickoff <= :now"),
    "awaiting_validation": ("Awaiting validation", "status IN ('data_submitted','validation_required')"),
    "analysis": ("Analyses in progress", "status = 'analysis_in_progress'"),
    "delayed": ("Delayed collection", f"status IN {PRE} AND ((collection_deadline IS NOT NULL AND collection_deadline < :now) OR kickoff < :yesterday)"),
}


def group_sql(key, alias="m"):
    """Group condition with columns qualified by a table alias (for joined queries)."""
    return re.sub(r"\b(status|kickoff|collection_deadline)\b", alias + r".\1", GROUPS[key][1])


def group_count(key):
    now = local_now()
    return scalar(f"SELECT COUNT(*) FROM matches WHERE {GROUPS[key][1]}",
                  _args(key, now))


def _args(key, now):
    sql = GROUPS[key][1]
    out = {}
    if ":now" in sql:
        out["now"] = now.strftime("%Y-%m-%d %H:%M:%S")
    if ":yesterday" in sql:
        from datetime import timedelta
        out["yesterday"] = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    return out


def outstanding_invoices():
    """Return (count, total balance) for issued, unpaid invoices."""
    rows = q("SELECT i.id, i.total - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS bal "
             "FROM invoices i WHERE i.status IN ('sent','partial')")
    rows = [r for r in rows if r["bal"] > 0.004]
    return len(rows), sum(r["bal"] for r in rows)


@bp.route("/")
def index():
    return redirect(url_for("dashboard.home") if g.get("user") else url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def home():
    if g.user["user_type"] == "client":
        return redirect(url_for("portal.home"))
    role = primary_role()
    now = local_now()
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")
    today = now.strftime("%Y-%m-%d")
    cards = []

    def card(label, value, href, tone="", sub=""):
        cards.append(dict(label=label, value=value, href=href, tone=tone, sub=sub))

    if has_perm("football.view"):
        card("Registered clubs", scalar("SELECT COUNT(*) FROM clubs"), url_for("crud.list_view", name="clubs"))
        card("Registered players", scalar("SELECT COUNT(*) FROM players"), url_for("crud.list_view", name="players"))
        card("Competitions", scalar("SELECT COUNT(*) FROM competitions"), url_for("crud.list_view", name="competitions"))
    if has_perm("match.view"):
        for key, tone in (("scheduled", ""), ("completed", "ok"), ("awaiting_collection", "warn"), ("awaiting_validation", "warn")):
            card(f"Matches {GROUPS[key][0].lower()}" if key in ("scheduled", "completed") else GROUPS[key][0],
                 group_count(key), url_for("matches.list_view", group=key), tone)
    if has_perm("analysis.view"):
        card("Analyses in progress", group_count("analysis"), url_for("matches.list_view", group="analysis"))
    if has_perm("report.view", "report.approve"):
        card("Reports awaiting approval", scalar("SELECT COUNT(*) FROM reports WHERE status='under_review'"),
             url_for("reports.list_view", status="under_review"), "warn")
        card("Reports delivered", scalar("SELECT COUNT(*) FROM reports WHERE status='delivered'"),
             url_for("reports.list_view", status="delivered"), "ok")
    if has_perm("clients.view"):
        card("Active clients", scalar("SELECT COUNT(*) FROM clients WHERE is_active=1"), url_for("crud.list_view", name="clients"))
        card("Open client requests", scalar("SELECT COUNT(*) FROM client_requests WHERE status='open'"), url_for("business.requests"), "warn")
    if has_perm("finance.summary"):
        n, bal = outstanding_invoices()
        card("Outstanding invoices", n, url_for("business.invoices", status="outstanding") if has_perm("finance.view") else "",
             "warn", sub=f"{get_setting('currency')} {bal:,.2f}" if has_perm("finance.view") else "")

    panels = {}
    uid = g.user["id"]
    if has_perm("tasks.own"):
        panels["tasks"] = q("SELECT * FROM tasks WHERE assigned_to=? AND status NOT IN ('done','cancelled') "
                            "ORDER BY COALESCE(due_date,'9999') LIMIT 8", (uid,))
    if has_perm("events.collect"):
        panels["my_assignments"] = q(
            "SELECT m.id, m.match_code, m.kickoff, m.status, m.collection_deadline, ht.name AS home, at.name AS away, ca.assignment_role "
            "FROM collection_assignments ca JOIN matches m ON m.id=ca.match_id JOIN teams ht ON ht.id=m.home_team_id "
            "JOIN teams at ON at.id=m.away_team_id WHERE ca.user_id=? AND ca.assignment_role IN ('collector','backup_collector') "
            "AND m.status NOT IN ('archived','cancelled') ORDER BY m.kickoff", (uid,))
    if role in ("operations_manager", "managing_director"):
        panels["delayed"] = q(
            "SELECT m.id, m.match_code, m.kickoff, m.status, m.collection_deadline, ht.name AS home, at.name AS away FROM matches m "
            "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
            f"WHERE {group_sql('delayed')} ORDER BY m.kickoff", _args("delayed", now))
        panels["unassigned"] = q(
            "SELECT m.id, m.match_code, m.kickoff, ht.name AS home, at.name AS away FROM matches m JOIN teams ht ON ht.id=m.home_team_id "
            "JOIN teams at ON at.id=m.away_team_id WHERE m.status IN ('scheduled','assigned','ready_for_collection') "
            "AND NOT EXISTS (SELECT 1 FROM collection_assignments ca WHERE ca.match_id=m.id AND ca.assignment_role='collector') "
            "ORDER BY m.kickoff LIMIT 8")
        panels["upcoming"] = q(
            "SELECT m.id, m.match_code, m.kickoff, m.status, ht.name AS home, at.name AS away FROM matches m JOIN teams ht ON ht.id=m.home_team_id "
            "JOIN teams at ON at.id=m.away_team_id WHERE m.kickoff >= ? AND m.status NOT IN ('cancelled','postponed','archived') "
            "ORDER BY m.kickoff LIMIT 6", (now_s,))
        panels["completeness"] = q(
            "SELECT m.id, m.match_code, ht.name AS home, at.name AS away, m.status, "
            "(SELECT COUNT(*) FROM appearances a WHERE a.match_id=m.id) AS apps, "
            "(SELECT COUNT(*) FROM match_events e WHERE e.match_id=m.id) AS events, "
            "(SELECT COUNT(*) FROM match_collection_scope s WHERE s.match_id=m.id AND s.collected=1) AS scopes, "
            "(SELECT COUNT(*) FROM validation_issues v WHERE v.match_id=m.id AND v.status='open' AND v.severity='error') AS errors "
            "FROM matches m JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
            "WHERE m.status NOT IN ('scheduled','cancelled','postponed','archived') ORDER BY m.kickoff DESC LIMIT 8")
    if role in ("football_analyst", "managing_director") or has_perm("events.validate"):
        panels["validation_queue"] = q(
            "SELECT m.id, m.match_code, m.kickoff, m.status, ht.name AS home, at.name AS away, "
            "(SELECT COUNT(*) FROM match_events e WHERE e.match_id=m.id) AS events FROM matches m "
            "JOIN teams ht ON ht.id=m.home_team_id JOIN teams at ON at.id=m.away_team_id "
            "WHERE m.status IN ('validation_required','data_submitted') ORDER BY m.kickoff")
    if has_perm("report.create"):
        panels["my_reports"] = q("SELECT id, title, status, report_type, updated_at FROM reports WHERE created_by=? "
                                 "AND status IN ('draft','returned','under_review') ORDER BY updated_at DESC LIMIT 8", (uid,))
    if has_perm("report.approve"):
        panels["to_approve"] = q("SELECT id, title, report_type, updated_at FROM reports WHERE status='under_review' ORDER BY updated_at")
    if has_perm("scouting.manage"):
        panels["scouting_mine"] = q("SELECT s.id, p.full_name, s.review_status, s.confidence, s.updated_at FROM scouting_reports s "
                                    "JOIN players p ON p.id=s.player_id WHERE s.analyst_id=? ORDER BY s.updated_at DESC LIMIT 8", (uid,))
        panels["video_counts"] = dict(videos=scalar("SELECT COUNT(*) FROM video_assets"), clips=scalar("SELECT COUNT(*) FROM video_clips"),
                                      pending=scalar("SELECT COUNT(*) FROM video_assets WHERE permission_status='pending'"))
    if has_perm("system.admin"):
        panels["tech"] = dict(
            last_backup=q("SELECT * FROM backup_logs WHERE action='backup' ORDER BY id DESC LIMIT 1", one=True),
            last_restore_test=q("SELECT * FROM backup_logs WHERE action='restore_test' ORDER BY id DESC LIMIT 1", one=True),
            errors=scalar("SELECT COUNT(*) FROM error_logs WHERE created_at >= datetime('now','-7 days')"),
            failed_imports=scalar("SELECT COUNT(*) FROM import_jobs WHERE status='failed' OR rows_failed>0"),
            users=scalar("SELECT COUNT(*) FROM users WHERE is_active=1 AND user_type='employee'"),
            locked=scalar("SELECT COUNT(*) FROM users WHERE locked_until IS NOT NULL AND locked_until > datetime('now')"))
    if has_perm("finance.summary") and role in ("finance_marketing_lead", "managing_director"):
        panels["finance"] = finance_summary(today, detailed=has_perm("finance.view"))
    if has_perm("marketing.manage") or has_perm("clients.view"):
        panels["followups"] = q(
            "SELECT 'Client' AS kind, name, next_followup, id AS rid FROM clients WHERE next_followup IS NOT NULL AND next_followup <= date(?, '+7 day') AND is_active=1 "
            "UNION ALL SELECT 'Prospect', name, next_followup, id FROM leads WHERE next_followup IS NOT NULL AND status NOT IN ('won','lost') "
            "AND next_followup <= date(?, '+7 day') ORDER BY next_followup LIMIT 10", (today, today))
    if has_perm("tasks.view_all"):
        panels["workload"] = q(
            "SELECT u.full_name, SUM(CASE WHEN t.status IN ('open','in_progress','blocked') THEN 1 ELSE 0 END) AS open_tasks, "
            "SUM(CASE WHEN t.status IN ('open','in_progress','blocked') AND t.due_date < ? THEN 1 ELSE 0 END) AS overdue "
            "FROM users u LEFT JOIN tasks t ON t.assigned_to=u.id WHERE u.user_type='employee' AND u.is_active=1 "
            "GROUP BY u.id ORDER BY overdue DESC, open_tasks DESC", (today,))
        panels["overdue_tasks"] = q("SELECT t.*, u.full_name FROM tasks t LEFT JOIN users u ON u.id=t.assigned_to WHERE t.status IN ('open','in_progress','blocked') "
                                    "AND t.due_date < ? ORDER BY t.due_date LIMIT 8", (today,))
    if has_perm("audit.view") and role == "managing_director":
        panels["audit"] = q("SELECT a.*, u.full_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id "
                            "WHERE a.action NOT LIKE 'login.%' ORDER BY a.id DESC LIMIT 8")
    title = C.ROLES[role]["dashboard_title"] if role else "Dashboard"
    return render_template("dashboard.html", cards=cards, panels=panels, title=title, role=role, today=today, now_s=now_s)


def finance_summary(today, detailed=False):
    ym = today[:7]
    income_m = scalar("SELECT SUM(amount) FROM payments WHERE substr(paid_date,1,7)=?", (ym,))
    exp_m = scalar("SELECT SUM(amount) FROM expenses WHERE substr(expense_date,1,7)=?", (ym,))
    n, bal = outstanding_invoices()
    overdue = q("SELECT i.id, i.invoice_number, i.due_date, c.name AS client, i.total - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS bal "
                "FROM invoices i JOIN clients c ON c.id=i.client_id WHERE i.status IN ('sent','partial') AND i.due_date < ? ORDER BY i.due_date", (today,))
    overdue = [r for r in overdue if r["bal"] > 0.004]
    months = q("SELECT m, SUM(inc) AS inc, SUM(exp) AS exp FROM ("
               "SELECT substr(paid_date,1,7) AS m, amount AS inc, 0 AS exp FROM payments "
               "UNION ALL SELECT substr(expense_date,1,7), 0, amount FROM expenses) GROUP BY m ORDER BY m DESC LIMIT 6")
    return dict(income_month=income_m, expenses_month=exp_m, outstanding_count=n, outstanding_total=bal,
                overdue=overdue, months=list(reversed([dict(r) for r in months])), detailed=detailed)
