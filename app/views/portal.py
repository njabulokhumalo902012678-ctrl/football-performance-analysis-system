"""Client portal: clients see only what has been explicitly shared with their organisation."""
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from ..db import ex, get_setting, q, scalar
from ..security import audit, client_id_for_user, client_required

bp = Blueprint("portal", __name__, url_prefix="/portal")


@bp.before_request
def _guard():
    if not g.get("user"):
        return redirect(url_for("auth.login", next=request.path))


def _shares(cid):
    """Latest non-revoked share per report for this client."""
    return q("SELECT s.*, r.title, r.report_type, r.status AS report_status FROM report_shares s JOIN reports r ON r.id=s.report_id "
             "WHERE s.client_id=? AND s.status='delivered' AND r.status='delivered' AND s.id IN "
             "(SELECT MAX(id) FROM report_shares WHERE client_id=? AND status='delivered' GROUP BY report_id) ORDER BY s.shared_at DESC", (cid, cid))


@bp.route("/")
@client_required
def home():
    cid = client_id_for_user()
    c = q("SELECT c.*, u.full_name AS contact FROM clients c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.id=?", (cid,), one=True)
    reqs = q("SELECT * FROM client_requests WHERE client_id=? ORDER BY id DESC LIMIT 20", (cid,))
    return render_template("portal/home.html", c=c, shares=_shares(cid), reqs=reqs, show_services=get_setting("portal_show_services", "1") == "1")


@bp.route("/report/<int:share_id>.pdf")
@client_required
def report_pdf(share_id):
    cid = client_id_for_user()
    s = q("SELECT s.*, r.status AS rstatus FROM report_shares s JOIN reports r ON r.id=s.report_id WHERE s.id=? AND s.client_id=?", (share_id, cid), one=True)
    if not s or s["status"] != "delivered" or s["rstatus"] != "delivered":
        abort(404)                  # another client's (or a withdrawn) report looks exactly like a missing one
    v = q("SELECT * FROM report_versions WHERE report_id=? AND version=?", (s["report_id"], s["version"]), one=True)
    path = Path(current_app.config["REPORT_DIR"]) / (v["pdf_path"] if v else "missing")
    if not v or not path.exists():
        abort(404)
    ex("UPDATE report_shares SET viewed_at=COALESCE(viewed_at, CURRENT_TIMESTAMP), downloaded_at=CURRENT_TIMESTAMP WHERE id=?", (share_id,))
    audit("portal.report_download", "reports", s["report_id"], {"share": share_id})
    return send_file(path, mimetype="application/pdf", download_name=f"report_{s['report_id']}.pdf")


@bp.route("/request", methods=["POST"])
@client_required
def new_request():
    kind = request.form.get("kind", "request")
    subj, msg = request.form.get("subject", "").strip(), request.form.get("message", "").strip()
    if kind not in ("request", "feedback") or not subj or not msg:
        flash("Enter a subject and a message.", "error")
    else:
        rid = ex("INSERT INTO client_requests (client_id, user_id, kind, subject, message) VALUES (?,?,?,?,?)",
                 (client_id_for_user(), g.user["id"], kind, subj[:190], msg[:3000]))
        audit("portal.request", "client_requests", rid)
        flash("Thank you - your message has been sent to our team.", "ok")
    return redirect(url_for("portal.home"))
