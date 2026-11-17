"""Football Data and Performance Analysis Company - management system (Flask application factory)."""
import json
import os
import secrets
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, g, render_template, request, session
from markupsafe import Markup, escape

from . import constants as C
from . import db as database
from . import security
from .forms import form_value

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"), instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    key_file = Path(app.instance_path) / "secret_key"
    if os.environ.get("FDPA_SECRET_KEY"):
        secret = os.environ["FDPA_SECRET_KEY"]
    else:
        if not key_file.exists():
            key_file.write_text(secrets.token_hex(32))
        secret = key_file.read_text().strip()

    app.config.update(
        SECRET_KEY=secret,
        DATABASE=os.environ.get("FDPA_DB", str(Path(app.instance_path) / "fdpa.sqlite3")),
        REPORT_DIR=str(Path(app.instance_path) / "reports"),
        VIDEO_DIR=str(Path(app.instance_path) / "videos"),
        BACKUP_DIR=str(BASE_DIR / "backups"),
        OUTBOX_DIR=str(Path(app.instance_path) / "outbox"),
        MAX_CONTENT_LENGTH=512 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FDPA_HTTPS", "0") == "1",   # set FDPA_HTTPS=1 in production
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    if test_config:
        app.config.update(test_config)
    for d in ("REPORT_DIR", "VIDEO_DIR", "BACKUP_DIR", "OUTBOX_DIR"):
        Path(app.config[d]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(database.close_db)
    app.jinja_env.globals.update(csrf_token=security.csrf_token, has_perm=security.has_perm, form_value=form_value)

    @app.before_request
    def _before():
        security.check_csrf()
        security.load_user()
        return security.enforce_session_rules()

    @app.after_request
    def _after(resp):
        con = g.get("db")
        if con is not None:
            if resp.status_code < 400:
                con.commit()
            else:
                con.rollback()
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy",
                                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                "script-src 'self'; frame-ancestors 'self'; object-src 'self'; frame-src 'self'")
        if request.endpoint != "static":
            resp.headers.setdefault("Cache-Control", "no-store")
        if app.config["SESSION_COOKIE_SECURE"]:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return resp

    # ------------------------------------------------------------------ template helpers
    @app.context_processor
    def _ctx():
        return dict(has_perm=security.has_perm, csrf_token=security.csrf_token, is_client=security.is_client,
                    company_name=database.get_setting("company_name", C.COMPANY_NAME),
                    company_tagline=database.get_setting("company_tagline", C.COMPANY_TAGLINE),
                    STATUS_LABEL=C.STATUS_LABEL, C=C, primary_role=security.primary_role, form_value=form_value, g=g)

    @app.template_filter("dt")
    def _dt(v, fmt="%d %b %Y %H:%M"):
        """Show a UTC timestamp in company local time."""
        if not v:
            return "-"
        try:
            d = datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return str(v)
        off = float(database.get_setting("timezone_offset_hours", "2") or 0)
        return (d + timedelta(hours=off)).strftime(fmt)

    @app.template_filter("ldt")
    def _ldt(v, fmt="%a %d %b %Y, %H:%M"):
        """Format an already-local datetime (kick-off, deadlines)."""
        if not v:
            return "-"
        s = str(v).replace("T", " ")
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:19] if len(s) > 10 else s, f).strftime(fmt if len(s) > 10 else "%d %b %Y")
            except ValueError:
                continue
        return str(v)

    @app.template_filter("money")
    def _money(v):
        cur = database.get_setting("currency", "SZL")
        try:
            return f"{cur} {float(v or 0):,.2f}"
        except (TypeError, ValueError):
            return "-"

    @app.template_filter("label")
    def _label(v):
        return str(v).replace("_", " ").capitalize() if v not in (None, "") else "-"

    @app.template_filter("badge")
    def _badge(v):
        tone = {"validated": "ok", "verified": "ok", "approved": "ok", "delivered": "ok", "paid": "ok", "done": "ok",
                "active": "ok", "won": "ok", "agreed": "ok", "data_validated": "ok", "delivered_to_client": "ok",
                "submitted": "info", "validation_required": "warn", "corrections_required": "bad", "returned": "bad",
                "overdue": "bad", "withdrawn": "bad", "open": "warn", "partial": "warn", "draft": "muted",
                "cancelled": "bad", "postponed": "warn", "lost": "bad", "urgent": "bad", "high": "warn",
                "unverified": "muted", "pending": "warn", "report_under_review": "info", "under_review": "info"}.get(str(v), "info")
        text = C.STATUS_LABEL.get(v) or str(v).replace("_", " ").capitalize()
        return Markup(f'<span class="badge {tone}">{escape(text)}</span>')

    @app.template_filter("json")
    def _json(v):
        return json.dumps(v)

    # ------------------------------------------------------------------ blueprints
    from .views import (admin, analysis, auth, business, collect, crud, dashboard, matches, portal, reports,
                        scouting, validate)
    for mod in (auth, dashboard, crud, matches, collect, validate, analysis, reports, scouting, business, portal, admin):
        app.register_blueprint(mod.bp)

    # ------------------------------------------------------------------ errors
    def _log_error(exc):
        try:
            database.ex("INSERT INTO error_logs (user_id, path, message, trace) VALUES (?,?,?,?)",
                        (g.user["id"] if g.get("user") else None, request.path, str(exc)[:500], traceback.format_exc()[-4000:]))
            g.db.commit()
        except Exception:      # logging must never break the error page
            pass

    @app.errorhandler(400)
    def _e400(e):
        return render_template("error.html", code=400, title="Request could not be processed",
                               message=getattr(e, "description", "The request was not valid.")), 400

    @app.errorhandler(403)
    def _e403(e):
        return render_template("error.html", code=403, title="Access denied",
                               message="Your role does not allow you to do this. If you think this is a mistake, ask the Technology Lead to review your permissions."), 403

    @app.errorhandler(404)
    def _e404(e):
        return render_template("error.html", code=404, title="Page not found", message="That record or page does not exist."), 404

    @app.errorhandler(413)
    def _e413(e):
        return render_template("error.html", code=413, title="File too large", message="The uploaded file is too large."), 413

    @app.errorhandler(Exception)
    def _e500(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        if g.get("db") is not None:
            g.db.rollback()
        _log_error(e)
        app.logger.exception("Unhandled error")
        return render_template("error.html", code=500, title="Something went wrong",
                               message="The problem has been logged for the Technology Lead. Nothing was saved from this action."), 500

    return app
