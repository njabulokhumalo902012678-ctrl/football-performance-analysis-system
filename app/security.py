"""Authentication helpers, role-based access control, CSRF protection and audit logging."""
import hmac
import json
import re
import secrets
import time
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import constants as C
from .db import ex, get_setting, q

PUBLIC_ENDPOINTS = {"auth.login", "auth.forgot", "auth.reset", "static", "auth.logout"}


# ----------------------------------------------------------------------------- passwords
def hash_password(pw):
    return generate_password_hash(pw, method="pbkdf2:sha256:600000")


def verify_password(h, pw):
    return check_password_hash(h, pw)


def password_problems(pw):
    probs = []
    if len(pw) < 10:
        probs.append("at least 10 characters")
    if not re.search(r"[a-z]", pw):
        probs.append("a lowercase letter")
    if not re.search(r"[A-Z]", pw):
        probs.append("an uppercase letter")
    if not re.search(r"\d", pw):
        probs.append("a number")
    return probs


# ----------------------------------------------------------------------------- csrf
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Security token missing or expired. Reload the page and try again.")


# ----------------------------------------------------------------------------- user / permissions
def load_user():
    g.user = None
    g.perms = set()
    g.role_codes = []
    uid = session.get("user_id")
    if not uid:
        return
    u = q("SELECT * FROM users WHERE id=? AND is_active=1", (uid,), one=True)
    if not u:
        session.clear()
        return
    g.user = u
    roles = q("SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=?", (uid,))
    g.role_codes = [r["code"] for r in roles]
    perms = q("SELECT DISTINCT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id "
              "JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=?", (uid,))
    g.perms = {p["code"] for p in perms}


def has_perm(*codes):
    return any(c in g.get("perms", set()) for c in codes)


def is_client():
    return g.get("user") is not None and g.user["user_type"] == "client"


def client_id_for_user():
    if not g.get("user"):
        return None
    r = q("SELECT client_id FROM client_users WHERE user_id=?", (g.user["id"],), one=True)
    return r["client_id"] if r else None


def primary_role():
    for code in C.PRIMARY_ROLE_ORDER:
        if code in g.get("role_codes", []):
            return code
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not g.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return f(*a, **kw)
    return wrapper


def perm_required(*codes):
    """User must hold at least one of the listed permissions."""
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not g.get("user"):
                return redirect(url_for("auth.login", next=request.path))
            if is_client():
                abort(403)
            if not has_perm(*codes):
                audit("access.denied", details={"path": request.path, "needs": list(codes)})
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


def client_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not g.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        if not is_client() or not client_id_for_user():
            abort(403)
        return f(*a, **kw)
    return wrapper


def enforce_session_rules():
    """Inactivity timeout, plus keeping client accounts inside the portal."""
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if session.get("user_id"):
        timeout = int(get_setting("session_timeout_minutes", "30") or 30) * 60
        last = session.get("last_seen", time.time())
        if time.time() - last > timeout:
            session.clear()
            flash("You were signed out after a period of inactivity. Please sign in again.", "info")
            return redirect(url_for("auth.login"))
        session["last_seen"] = time.time()
    if g.get("user") and is_client():
        if not (request.endpoint or "").startswith("portal.") and request.endpoint not in ("auth.logout", "static", "auth.change_password"):
            return redirect(url_for("portal.home"))
    return None


# ----------------------------------------------------------------------------- audit
def audit(action, entity=None, entity_id=None, details=None, user_id=None):
    uid = user_id if user_id is not None else (g.user["id"] if g.get("user") else None)
    ip = request.remote_addr if request else None
    ex("INSERT INTO audit_logs (user_id, action, entity, entity_id, details, ip_address) VALUES (?,?,?,?,?,?)",
       (uid, action, entity, entity_id, json.dumps(details, default=str) if details is not None else None, ip))


def diff(old, new, fields):
    out = {}
    for f in fields:
        o, n = (old[f] if old is not None else None), new.get(f)
        if str(o if o is not None else "") != str(n if n is not None else ""):
            out[f] = {"from": o, "to": n}
    return out
