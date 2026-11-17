"""Login, logout, password reset and password change."""
import hashlib
import os
import secrets
import smtplib
import time
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from ..db import ex, q, utc_str, utcnow
from ..security import audit, hash_password, login_required, password_problems, verify_password

bp = Blueprint("auth", __name__)
MAX_FAILS = 5
LOCK_MINUTES = 15


def _safe_next(target):
    if not target:
        return None
    u = urlparse(target)
    return target if (not u.netloc and not u.scheme and target.startswith("/") and not target.startswith("//")) else None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip().lower()
        pw = request.form.get("password", "")
        u = q("SELECT * FROM users WHERE lower(username)=? OR lower(email)=?", (ident, ident), one=True)
        generic = "Username/email or password is not correct."
        if u and u["locked_until"] and u["locked_until"] > utc_str():
            audit("login.locked", "users", u["id"], user_id=u["id"])
            flash("This account is temporarily locked after too many failed attempts. Try again in a few minutes.", "error")
        elif u and u["is_active"] and verify_password(u["password_hash"], pw):
            session.clear()
            session["user_id"] = u["id"]
            session["last_seen"] = time.time()
            session.permanent = False
            ex("UPDATE users SET failed_logins=0, locked_until=NULL, last_login_at=CURRENT_TIMESTAMP WHERE id=?", (u["id"],))
            audit("login.success", "users", u["id"], user_id=u["id"])
            if u["must_change_password"]:
                flash("Please choose a new password before continuing.", "info")
                return redirect(url_for("auth.change_password"))
            return redirect(_safe_next(request.args.get("next")) or url_for("dashboard.home"))
        else:
            if u:
                fails = u["failed_logins"] + 1
                lock = (utcnow() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S") if fails >= MAX_FAILS else None
                ex("UPDATE users SET failed_logins=?, locked_until=COALESCE(?, locked_until) WHERE id=?", (0 if lock else fails, lock, u["id"]))
                audit("login.failed", "users", u["id"], {"deactivated": not u["is_active"]}, user_id=u["id"])
            else:
                audit("login.failed", details={"identifier": ident[:60]}, user_id=None)
            flash(generic, "error")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    if g.get("user"):
        audit("logout", "users", g.user["id"])
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


def _send_mail(to, subject, body):
    """Write to the outbox folder; also send through SMTP when FDPA_SMTP_HOST is configured."""
    out = Path(current_app.config["OUTBOX_DIR"])
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{int(time.time())}_{secrets.token_hex(3)}.txt").write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
    host = os.environ.get("FDPA_SMTP_HOST")
    if host:
        try:
            msg = EmailMessage()
            msg["To"], msg["Subject"] = to, subject
            msg["From"] = os.environ.get("FDPA_SMTP_FROM", "no-reply@example.com")
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("FDPA_SMTP_PORT", "587")), timeout=10) as s:
                s.starttls()
                if os.environ.get("FDPA_SMTP_USER"):
                    s.login(os.environ["FDPA_SMTP_USER"], os.environ.get("FDPA_SMTP_PASSWORD", ""))
                s.send_message(msg)
        except Exception as exc:     # never reveal mail problems to the requester
            current_app.logger.warning("SMTP send failed: %s", exc)


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = q("SELECT * FROM users WHERE lower(email)=? AND is_active=1", (email,), one=True)
        if u:
            token = secrets.token_urlsafe(32)
            ex("INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?,?,?)",
               (u["id"], hashlib.sha256(token.encode()).hexdigest(), (utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")))
            link = request.host_url.rstrip("/") + url_for("auth.reset", token=token)
            _send_mail(u["email"], "Reset your password", f"Hello {u['full_name']},\n\nUse this link within one hour to choose a new password:\n{link}\n\nIf you did not ask for this, ignore this message.")
            audit("password.reset_requested", "users", u["id"], user_id=u["id"])
        flash("If that email belongs to an active account, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    h = hashlib.sha256(token.encode()).hexdigest()
    r = q("SELECT * FROM password_resets WHERE token_hash=? AND used_at IS NULL AND expires_at > ?", (h, utc_str()), one=True)
    if not r:
        flash("This reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
        probs = password_problems(pw)
        if pw != pw2:
            flash("The two passwords do not match.", "error")
        elif probs:
            flash("Password needs: " + ", ".join(probs) + ".", "error")
        else:
            ex("UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL, must_change_password=0 WHERE id=?", (hash_password(pw), r["user_id"]))
            ex("UPDATE password_resets SET used_at=CURRENT_TIMESTAMP WHERE id=?", (r["id"],))
            audit("password.reset", "users", r["user_id"], user_id=r["user_id"])
            flash("Password changed. You can now sign in.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html")


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        cur, pw, pw2 = request.form.get("current", ""), request.form.get("password", ""), request.form.get("password2", "")
        probs = password_problems(pw)
        if not verify_password(g.user["password_hash"], cur):
            flash("Your current password is not correct.", "error")
        elif pw != pw2:
            flash("The two new passwords do not match.", "error")
        elif probs:
            flash("Password needs: " + ", ".join(probs) + ".", "error")
        elif pw == cur:
            flash("Choose a password different from the current one.", "error")
        else:
            ex("UPDATE users SET password_hash=?, must_change_password=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (hash_password(pw), g.user["id"]))
            audit("password.changed", "users", g.user["id"])
            flash("Password updated.", "ok")
            return redirect(url_for("dashboard.home"))
    return render_template("auth/change_password.html")
