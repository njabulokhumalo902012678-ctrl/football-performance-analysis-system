"""Client management, finance (invoices, payments), marketing follow-up and task management."""
import secrets
from datetime import date, datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import constants as C
from ..db import ex, get_setting, local_now, q, scalar
from ..forms import F, parse_form
from ..security import audit, diff, hash_password, has_perm, perm_required
from .dashboard import finance_summary, outstanding_invoices

bp = Blueprint("business", __name__)
EMP = ("users", "full_name", "user_type='employee' AND is_active=1")


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))
    if g.user["user_type"] == "client":
        abort(403)


def today_s():
    return local_now().strftime("%Y-%m-%d")


# ============================================================================= clients
@bp.route("/clients/<int:cid>")
@perm_required("clients.view")
def client_detail(cid):
    c = q("SELECT c.*, u.full_name AS contact FROM clients c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.id=?", (cid,), one=True)
    if not c:
        abort(404)
    accounts = q("SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.last_login_at FROM client_users cu JOIN users u ON u.id=cu.user_id WHERE cu.client_id=?", (cid,))
    reports = q("SELECT s.*, r.title, r.report_type FROM report_shares s JOIN reports r ON r.id=s.report_id WHERE s.client_id=? ORDER BY s.id DESC", (cid,))
    history = q("SELECT h.*, u.full_name FROM contact_history h LEFT JOIN users u ON u.id=h.user_id WHERE h.client_id=? ORDER BY h.contact_date DESC", (cid,))
    requests_ = q("SELECT * FROM client_requests WHERE client_id=? ORDER BY id DESC LIMIT 10", (cid,))
    invoices = q("SELECT i.*, i.total - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS balance FROM invoices i WHERE i.client_id=? ORDER BY i.id DESC", (cid,)) \
        if has_perm("finance.view") else []
    return render_template("business/client_detail.html", c=c, accounts=accounts, reports=reports, history=history, requests=requests_,
                           invoices=invoices, can_manage=has_perm("clients.manage"), channels=["phone", "email", "meeting", "whatsapp", "social media", "other"])


@bp.route("/clients/<int:cid>/account", methods=["POST"])
@perm_required("clients.manage")
def client_account(cid):
    c = q("SELECT * FROM clients WHERE id=?", (cid,), one=True)
    if not c:
        abort(404)
    name, email = request.form.get("full_name", "").strip(), request.form.get("email", "").strip().lower()
    username = request.form.get("username", "").strip().lower() or email
    if not name or "@" not in email:
        flash("Enter the person's name and a valid email address.", "error")
    elif scalar("SELECT COUNT(*) FROM users WHERE lower(username)=? OR lower(email)=?", (username, email)):
        flash("That username or email is already used by another account.", "error")
    else:
        temp = secrets.token_urlsafe(9) + "A1"
        uid = ex("INSERT INTO users (username, email, full_name, password_hash, user_type, must_change_password) VALUES (?,?,?,?, 'client', 1)",
                 (username, email, name, hash_password(temp)))
        ex("INSERT INTO user_roles (user_id, role_id) SELECT ?, id FROM roles WHERE code='client'", (uid,))
        ex("INSERT INTO client_users (client_id, user_id) VALUES (?,?)", (cid, uid))
        audit("client.account_create", "users", uid, {"client": cid})
        flash(f"Portal account created. Username: {username}  Temporary password (shown once): {temp}", "ok")
    return redirect(url_for("business.client_detail", cid=cid))


@bp.route("/clients/<int:cid>/account/<int:uid>/toggle", methods=["POST"])
@perm_required("clients.manage")
def client_account_toggle(cid, uid):
    if not scalar("SELECT COUNT(*) FROM client_users WHERE client_id=? AND user_id=?", (cid, uid)):
        abort(404)
    ex("UPDATE users SET is_active = 1 - is_active WHERE id=?", (uid,))
    audit("client.account_toggle", "users", uid)
    return redirect(url_for("business.client_detail", cid=cid))


@bp.route("/clients/<int:cid>/contact", methods=["POST"])
def client_contact(cid):
    if not has_perm("clients.manage", "marketing.manage"):
        abort(403)
    summ = request.form.get("summary", "").strip()
    if summ and scalar("SELECT COUNT(*) FROM clients WHERE id=?", (cid,)):
        ex("INSERT INTO contact_history (client_id, contact_date, channel, summary, user_id) VALUES (?,?,?,?,?)",
           (cid, today_s(), request.form.get("channel", "other")[:40], summ[:2000], g.user["id"]))
        nf = request.form.get("next_followup", "").strip()
        if nf:
            try:
                datetime.strptime(nf, "%Y-%m-%d")
                ex("UPDATE clients SET next_followup=? WHERE id=?", (nf, cid))
            except ValueError:
                flash("Follow-up date was not valid and was ignored.", "error")
        audit("client.contact", "clients", cid)
        flash("Contact recorded.", "ok")
    return redirect(url_for("business.client_detail", cid=cid))


@bp.route("/requests")
@perm_required("clients.view")
def requests():
    rows = q("SELECT r.*, c.name AS client, u.full_name AS who FROM client_requests r JOIN clients c ON c.id=r.client_id LEFT JOIN users u ON u.id=r.user_id "
             "ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END, r.id DESC")
    return render_template("business/requests.html", rows=rows, can_respond=has_perm("clients.manage", "marketing.manage"))


@bp.route("/requests/<int:rid>", methods=["POST"])
def request_respond(rid):
    if not has_perm("clients.manage", "marketing.manage"):
        abort(403)
    r = q("SELECT * FROM client_requests WHERE id=?", (rid,), one=True)
    if not r:
        abort(404)
    resp = request.form.get("response", "").strip()
    if not resp:
        flash("Write a response.", "error")
    else:
        ex("UPDATE client_requests SET response=?, status='closed', responded_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (resp[:3000], g.user["id"], rid))
        audit("request.respond", "client_requests", rid)
        flash("Response saved. The client can see it in their portal.", "ok")
    return redirect(url_for("business.requests"))


# ============================================================================= leads
@bp.route("/leads/<int:lid>")
@perm_required("marketing.manage")
def lead_detail(lid):
    l = q("SELECT l.*, u.full_name AS owner FROM leads l LEFT JOIN users u ON u.id=l.assigned_user_id WHERE l.id=?", (lid,), one=True)
    if not l:
        abort(404)
    history = q("SELECT h.*, u.full_name FROM contact_history h LEFT JOIN users u ON u.id=h.user_id WHERE h.lead_id=? ORDER BY h.contact_date DESC, h.id DESC", (lid,))
    return render_template("business/lead_detail.html", l=l, history=history, channels=["phone", "email", "meeting", "whatsapp", "social media", "other"])


@bp.route("/leads/<int:lid>/contact", methods=["POST"])
@perm_required("marketing.manage")
def lead_contact(lid):
    l = q("SELECT * FROM leads WHERE id=?", (lid,), one=True)
    if not l:
        abort(404)
    summ = request.form.get("summary", "").strip()
    if not summ:
        flash("Describe the contact.", "error")
    else:
        ex("INSERT INTO contact_history (lead_id, contact_date, channel, summary, user_id) VALUES (?,?,?,?,?)",
           (lid, today_s(), request.form.get("channel", "other")[:40], summ[:2000], g.user["id"]))
        nf = request.form.get("next_followup", "").strip()
        if nf:
            try:
                datetime.strptime(nf, "%Y-%m-%d")
                ex("UPDATE leads SET next_followup=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (nf, lid))
            except ValueError:
                pass
        if l["status"] == "new":
            ex("UPDATE leads SET status='contacted' WHERE id=?", (lid,))
        flash("Contact recorded.", "ok")
    return redirect(url_for("business.lead_detail", lid=lid))


@bp.route("/leads/<int:lid>/convert", methods=["POST"])
@perm_required("marketing.manage")
def lead_convert(lid):
    if not has_perm("clients.manage"):
        abort(403)
    l = q("SELECT * FROM leads WHERE id=?", (lid,), one=True)
    if not l or l["converted_client_id"]:
        abort(400, "This prospect is already a client.")
    cid = ex("INSERT INTO clients (client_type, name, contact_person, email, phone, agreement_status, assigned_user_id, notes) VALUES (?,?,?,?,?,'prospect',?,?)",
             (l["org_type"] or "Other football organisation", l["name"], l["contact_person"], l["email"], l["phone"], l["assigned_user_id"], l["notes"]))
    ex("UPDATE leads SET converted_client_id=?, status='won', updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid, lid))
    audit("lead.convert", "leads", lid, {"client": cid})
    flash("Prospect converted to a client.", "ok")
    return redirect(url_for("business.client_detail", cid=cid))


# ============================================================================= finance
def balance_of(inv_id):
    inv = q("SELECT total FROM invoices WHERE id=?", (inv_id,), one=True)
    paid = scalar("SELECT SUM(amount) FROM payments WHERE invoice_id=?", (inv_id,), 0.0)
    return round(inv["total"] - paid, 2), round(paid, 2)


def _parse_items(form):
    items, errs = [], []
    descs, qtys, prices, svcs = form.getlist("desc"), form.getlist("qty"), form.getlist("price"), form.getlist("service")
    for i, d in enumerate(descs):
        d = d.strip()
        if not d and not (qtys[i] if i < len(qtys) else "").strip():
            continue
        try:
            qty = float(qtys[i]) if i < len(qtys) else 1
            price = float(prices[i]) if i < len(prices) else 0
        except ValueError:
            errs.append(f"Line {i + 1}: quantity and price must be numbers.")
            continue
        if not d:
            errs.append(f"Line {i + 1}: description is required.")
        elif qty <= 0 or price < 0:
            errs.append(f"Line {i + 1}: quantity must be above zero and price cannot be negative.")
        else:
            sid = int(svcs[i]) if i < len(svcs) and svcs[i].isdigit() and scalar("SELECT COUNT(*) FROM services WHERE id=?", (int(svcs[i]),)) else None
            items.append((sid, d[:255], qty, price, round(qty * price, 2)))
    if not items and not errs:
        errs.append("Add at least one invoice line.")
    return items, errs


def _next_number():
    prefix = get_setting("invoice_prefix", "INV")
    year = datetime.now().year
    n = scalar("SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE ?", (f"{prefix}-{year}-%",)) + 1
    while scalar("SELECT COUNT(*) FROM invoices WHERE invoice_number=?", (f"{prefix}-{year}-{n:04d}",)):
        n += 1
    return f"{prefix}-{year}-{n:04d}"


@bp.route("/finance/")
@perm_required("finance.view")
def finance_home():
    summ = finance_summary(today_s(), detailed=True)
    by_client = q("SELECT c.name, SUM(i.total) AS billed, COALESCE(SUM((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id)),0) AS paid "
                  "FROM invoices i JOIN clients c ON c.id=i.client_id WHERE i.status!='void' GROUP BY c.id ORDER BY billed DESC")
    by_cat = q("SELECT category, SUM(amount) AS total FROM expenses GROUP BY category ORDER BY total DESC")
    proj = q("SELECT m.match_code, SUM(e.amount) AS total FROM expenses e JOIN matches m ON m.id=e.related_match_id GROUP BY m.id ORDER BY total DESC LIMIT 10")
    return render_template("business/finance.html", s=summ, by_client=by_client, by_cat=by_cat, proj=proj)


@bp.route("/finance/invoices")
@perm_required("finance.view")
def invoices():
    st = request.args.get("status", "")
    where, args = ["1=1"], []
    if st == "outstanding":
        where.append("i.status IN ('sent','partial')")
    elif st:
        where.append("i.status=?")
        args.append(st)
    rows = q("SELECT i.*, c.name AS client, i.total - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS balance "
             f"FROM invoices i JOIN clients c ON c.id=i.client_id WHERE {' AND '.join(where)} ORDER BY i.id DESC", args)
    return render_template("business/invoices.html", rows=rows, st=st, today=today_s(), can_manage=has_perm("finance.manage"))


@bp.route("/finance/invoices/new", methods=["GET", "POST"])
@perm_required("finance.manage")
def invoice_new():
    clients = q("SELECT id, name FROM clients WHERE is_active=1 ORDER BY name")
    services = q("SELECT * FROM services WHERE is_active=1 ORDER BY name")
    proposals = q("SELECT id, title FROM proposals WHERE status='accepted' ORDER BY id DESC")
    if request.method == "POST":
        errs = []
        cid = request.form.get("client_id", type=int)
        if not cid or not scalar("SELECT COUNT(*) FROM clients WHERE id=?", (cid,)):
            errs.append("Choose a client.")
        try:
            issue = datetime.strptime(request.form.get("issue_date", ""), "%Y-%m-%d").date()
            due = datetime.strptime(request.form.get("due_date", ""), "%Y-%m-%d").date()
            if due < issue:
                errs.append("Due date cannot be before the issue date.")
        except ValueError:
            errs.append("Enter valid issue and due dates.")
        try:
            rate = float(request.form.get("tax_rate", "0") or 0)
            if not 0 <= rate <= 100:
                raise ValueError
        except ValueError:
            errs.append("Tax rate must be between 0 and 100.")
            rate = 0
        items, ierrs = _parse_items(request.form)
        errs += ierrs
        if errs:
            for e in errs:
                flash(e, "error")
            return render_template("business/invoice_form.html", clients=clients, services=services, proposals=proposals, form=request.form, today=today_s(),
                                   default_tax=get_setting("default_tax_rate", "0")), 422
        subtotal = round(sum(i[4] for i in items), 2)
        tax = round(subtotal * rate / 100, 2)
        pid = request.form.get("proposal_id", type=int) or None
        inv = ex("INSERT INTO invoices (invoice_number, client_id, proposal_id, issue_date, due_date, status, subtotal, tax_rate, tax_amount, total, notes, created_by) "
                 "VALUES (?,?,?,?,?,'draft',?,?,?,?,?,?)", (_next_number(), cid, pid, str(issue), str(due), subtotal, rate, tax, round(subtotal + tax, 2),
                                                            request.form.get("notes", "")[:1000] or None, g.user["id"]))
        for it in items:
            ex("INSERT INTO invoice_items (invoice_id, service_id, description, quantity, unit_price, line_total) VALUES (?,?,?,?,?,?)", (inv, *it))
        audit("invoice.create", "invoices", inv, {"total": round(subtotal + tax, 2), "lines": len(items)})
        flash("Invoice created as a draft. Mark it as sent when you issue it to the client.", "ok")
        return redirect(url_for("business.invoice_detail", iid=inv))
    return render_template("business/invoice_form.html", clients=clients, services=services, proposals=proposals, form=None, today=today_s(),
                           default_tax=get_setting("default_tax_rate", "0"))


@bp.route("/finance/invoices/<int:iid>")
@perm_required("finance.view")
def invoice_detail(iid):
    inv = q("SELECT i.*, c.name AS client, c.email AS client_email FROM invoices i JOIN clients c ON c.id=i.client_id WHERE i.id=?", (iid,), one=True)
    if not inv:
        abort(404)
    items = q("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (iid,))
    pays = q("SELECT p.*, u.full_name FROM payments p LEFT JOIN users u ON u.id=p.recorded_by WHERE p.invoice_id=? ORDER BY p.paid_date, p.id", (iid,))
    bal, paid = balance_of(iid)
    log = q("SELECT a.*, u.full_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity IN ('invoices') AND a.entity_id=? ORDER BY a.id DESC", (iid,))
    return render_template("business/invoice_detail.html", inv=inv, items=items, pays=pays, balance=bal, paid=paid, log=log, today=today_s(),
                           can_manage=has_perm("finance.manage"), print_view=request.args.get("print") == "1")


@bp.route("/finance/invoices/<int:iid>/status", methods=["POST"])
@perm_required("finance.manage")
def invoice_status(iid):
    inv = q("SELECT * FROM invoices WHERE id=?", (iid,), one=True)
    if not inv:
        abort(404)
    act = request.form.get("action")
    bal, paid = balance_of(iid)
    if act == "send" and inv["status"] == "draft":
        ex("UPDATE invoices SET status='sent', updated_at=CURRENT_TIMESTAMP WHERE id=?", (iid,))
    elif act == "void" and inv["status"] in ("draft", "sent") and paid == 0:
        ex("UPDATE invoices SET status='void', updated_at=CURRENT_TIMESTAMP WHERE id=?", (iid,))
    else:
        flash("That action is not allowed for this invoice (invoices with payments cannot be voided).", "error")
        return redirect(url_for("business.invoice_detail", iid=iid))
    audit(f"invoice.{act}", "invoices", iid, {"reason": request.form.get("reason", "")[:200]})
    flash("Invoice updated.", "ok")
    return redirect(url_for("business.invoice_detail", iid=iid))


@bp.route("/finance/invoices/<int:iid>/payment", methods=["POST"])
@perm_required("finance.manage")
def payment_add(iid):
    inv = q("SELECT * FROM invoices WHERE id=?", (iid,), one=True)
    if not inv or inv["status"] not in ("sent", "partial"):
        flash("Payments can only be recorded against issued invoices with an outstanding balance.", "error")
        return redirect(url_for("business.invoice_detail", iid=iid))
    try:
        amount = round(float(request.form.get("amount", "")), 2)
        pd = datetime.strptime(request.form.get("paid_date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid amount and payment date.", "error")
        return redirect(url_for("business.invoice_detail", iid=iid))
    bal, _ = balance_of(iid)
    if amount <= 0:
        flash("The payment must be above zero.", "error")
    elif amount > bal + 0.004:
        flash(f"The payment is more than the outstanding balance ({bal:,.2f}).", "error")
    else:
        pid = ex("INSERT INTO payments (invoice_id, paid_date, amount, method, reference, recorded_by) VALUES (?,?,?,?,?,?)",
                 (iid, str(pd), amount, request.form.get("method", "")[:40] or None, request.form.get("reference", "")[:120] or None, g.user["id"]))
        new_bal, _ = balance_of(iid)
        ex("UPDATE invoices SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", ("paid" if new_bal <= 0.004 else "partial", iid))
        audit("payment.record", "invoices", iid, {"payment": pid, "amount": amount, "balance_after": new_bal})
        flash("Payment recorded.", "ok")
    return redirect(url_for("business.invoice_detail", iid=iid))


# ============================================================================= tasks
TASK_FIELDS = [
    F("title", "Task title", req=True), F("description", "Description", "textarea"),
    F("assigned_to", "Responsible employee", "fk", fk=EMP, req=True),
    F("department", "Department", "select", options=C.DEPARTMENTS), F("priority", "Priority", "select", options=C.PRIORITIES, req=True, default="normal"),
    F("due_date", "Due date", "date"), F("status", "Status", "select", options=C.TASK_STATUSES, req=True, default="open"),
    F("related_type", "Related to", "select", options=["match", "client", "project"]), F("related_id", "Related record ID", "int"),
    F("notes", "Supporting notes or file references", "textarea"),
]


def _task_scope():
    if has_perm("tasks.view_all"):
        return "1=1", []
    return "(t.assigned_to=? OR t.created_by=?)", [g.user["id"], g.user["id"]]


@bp.route("/tasks/")
@perm_required("tasks.own", "tasks.view_all")
def tasks():
    scope, args = _task_scope()
    where = [scope]
    f = request.args.get("filter", "")
    if f == "mine":
        where.append("t.assigned_to=?")
        args.append(g.user["id"])
    elif f == "overdue":
        where.append("t.status IN ('open','in_progress','blocked') AND t.due_date < ?")
        args.append(today_s())
    st = request.args.get("status", "")
    if st:
        where.append("t.status=?")
        args.append(st)
    dep = request.args.get("dept", "")
    if dep:
        where.append("t.department=?")
        args.append(dep)
    rows = q("SELECT t.*, u.full_name AS who FROM tasks t LEFT JOIN users u ON u.id=t.assigned_to "
             f"WHERE {' AND '.join(where)} ORDER BY CASE t.status WHEN 'done' THEN 1 WHEN 'cancelled' THEN 1 ELSE 0 END, COALESCE(t.due_date,'9999'), t.id DESC LIMIT 300", args)
    return render_template("business/tasks.html", rows=rows, f=f, st=st, dep=dep, today=today_s(), can_manage=has_perm("tasks.manage"),
                           departments=C.DEPARTMENTS, statuses=C.TASK_STATUSES)


def _task_form(t=None):
    if request.method == "POST":
        vals, errs = parse_form(TASK_FIELDS, request.form)
        if errs:
            flash("Some details need attention.", "error")
            return render_template("business/task_form.html", t=t, fields=TASK_FIELDS, form=request.form, errs=errs), 422
        done = vals["status"] == "done"
        names = list(vals)
        if t:
            ex("UPDATE tasks SET " + ", ".join(f"{n}=?" for n in names) + ", completed_at=CASE WHEN ?=1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE NULL END, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               [vals[n] for n in names] + [1 if done else 0, t["id"]])
            audit("task.update", "tasks", t["id"], diff(t, vals, names))
        else:
            tid = ex(f"INSERT INTO tasks ({', '.join(names)}, created_by, completed_at) VALUES ({', '.join('?' * len(names))}, ?, ?)",
                     [vals[n] for n in names] + [g.user["id"], utc() if done else None])
            audit("task.create", "tasks", tid)
        flash("Task saved.", "ok")
        return redirect(url_for("business.tasks"))
    return render_template("business/task_form.html", t=t, fields=TASK_FIELDS, form=None, errs={})


def utc():
    from ..db import utc_str
    return utc_str()


@bp.route("/tasks/new", methods=["GET", "POST"])
@perm_required("tasks.manage")
def task_new():
    return _task_form(None)


@bp.route("/tasks/<int:tid>/edit", methods=["GET", "POST"])
@perm_required("tasks.manage")
def task_edit(tid):
    t = q("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
    if not t:
        abort(404)
    return _task_form(t)


@bp.route("/tasks/<int:tid>/status", methods=["POST"])
@perm_required("tasks.own", "tasks.view_all")
def task_status(tid):
    t = q("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
    if not t:
        abort(404)
    if not (t["assigned_to"] == g.user["id"] or has_perm("tasks.manage")):
        abort(403)
    new = request.form.get("status")
    if new not in C.TASK_STATUSES:
        abort(400)
    ex("UPDATE tasks SET status=?, completed_at=CASE WHEN ?='done' THEN CURRENT_TIMESTAMP ELSE NULL END, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, new, tid))
    audit("task.status", "tasks", tid, {"from": t["status"], "to": new})
    return redirect(request.referrer or url_for("business.tasks"))


# ============================================================================= marketing summary
@bp.route("/marketing/")
@perm_required("marketing.manage")
def marketing():
    pipeline = q("SELECT status, COUNT(*) AS n FROM leads GROUP BY status")
    campaigns = q("SELECT * FROM marketing_campaigns ORDER BY COALESCE(start_date,'0000') DESC LIMIT 10")
    feedback = q("SELECT r.*, c.name AS client FROM client_requests r JOIN clients c ON c.id=r.client_id WHERE r.kind='feedback' ORDER BY r.id DESC LIMIT 10")
    due = q("SELECT * FROM leads WHERE next_followup IS NOT NULL AND next_followup <= date(?, '+7 day') AND status NOT IN ('won','lost') ORDER BY next_followup", (today_s(),))
    return render_template("business/marketing.html", pipeline=pipeline, campaigns=campaigns, feedback=feedback, due=due)
