"""SQLite data layer (all SQL uses bound parameters - never string-formatted values)."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app, g

from . import constants as C

SCHEMA = Path(__file__).with_name("schema.sql")


def get_db():
    if "db" not in g:
        con = sqlite3.connect(current_app.config["DATABASE"], timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        g.db = con
    return g.db


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def ex(sql, args=()):
    """Execute a write statement; returns lastrowid. Commit happens at end of a successful request."""
    cur = get_db().execute(sql, args)
    rid = cur.lastrowid
    cur.close()
    return rid


def scalar(sql, args=(), default=0):
    r = q(sql, args, one=True)
    if r is None or r[0] is None:
        return default
    return r[0]


def close_db(exc=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def utcnow():
    return datetime.utcnow()


def utc_str():
    return utcnow().strftime("%Y-%m-%d %H:%M:%S")


def local_now():
    """Company local time (UTC + configured offset). Deadlines and kick-offs are entered in local time."""
    off = float(get_setting("timezone_offset_hours", "2") or 0)
    return utcnow() + timedelta(hours=off)


def local_now_str():
    return local_now().strftime("%Y-%m-%d %H:%M:%S")


def get_setting(key, default=None):
    try:
        r = q("SELECT svalue FROM settings WHERE skey = ?", (key,), one=True)
    except sqlite3.Error:
        return default
    return r["svalue"] if r else default


def set_setting(key, value):
    ex("INSERT INTO settings (skey, svalue, updated_at) VALUES (?,?,CURRENT_TIMESTAMP) "
       "ON CONFLICT(skey) DO UPDATE SET svalue=excluded.svalue, updated_at=CURRENT_TIMESTAMP", (key, str(value)))


# ---------------------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "company_name": C.COMPANY_NAME,
    "company_tagline": C.COMPANY_TAGLINE,
    "session_timeout_minutes": "30",
    "timezone_offset_hours": "2",
    "currency": "SZL",
    "invoice_prefix": "INV",
    "default_tax_rate": "0",
    "confidentiality_statement": "This report is confidential and prepared exclusively for the named client. "
                                 "It must not be copied, shared or published without written permission from "
                                 "the Football Data and Performance Analysis Company.",
    "rating_rubric": "Analyst rating (0-10) is a documented professional judgement, not a computed statistic. "
                     "5.0 = below the standard expected for the match context; 6.0 = acceptable, limited impact; "
                     "7.0 = solid, contributed positively to the team's plan; 8.0 = influential, clearly "
                     "decisive actions; 9.0+ = exceptional. The rating must be supported by the evidence "
                     "listed in the report and by video where available. Ratings are given only by an "
                     "authorised analyst.",
    "retention_note": "Match, player and report records are retained for 5 years unless the client agreement states otherwise.",
}


def init_db(db_path):
    """Create a fresh database from schema.sql and seed reference data."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        raise RuntimeError(f"{db_path} already exists - refusing to overwrite.")
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    seed_reference(con)
    con.commit()
    con.close()


def seed_reference(con):
    """Roles, permissions, event types, metric definitions, settings, default data source (idempotent)."""
    from .metrics import METRICS
    cur = con.cursor()
    for code, desc in C.PERMISSIONS.items():
        cur.execute("INSERT OR IGNORE INTO permissions (code, description) VALUES (?,?)", (code, desc))
    for code, r in C.ROLES.items():
        cur.execute("INSERT OR IGNORE INTO roles (code, name, description, dashboard_title, is_primary) VALUES (?,?,?,?,?)",
                    (code, r["name"], r["description"], r["dashboard_title"], r["primary"]))
        rid = cur.execute("SELECT id FROM roles WHERE code=?", (code,)).fetchone()[0]
        for p in r["perms"]:
            pid = cur.execute("SELECT id FROM permissions WHERE code=?", (p,)).fetchone()[0]
            cur.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?,?)", (rid, pid))
    for (code, name, cat, scope, outcomes, needs_player, rel, coords, sp, sort) in C.EVENT_TYPES:
        cur.execute("INSERT OR IGNORE INTO event_types (code,name,category,scope_category,outcomes,needs_player,"
                    "related_label,uses_coords,uses_set_piece,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (code, name, cat, scope, outcomes, needs_player, rel, coords, sp, sort))
    for m in METRICS:
        cur.execute("INSERT OR REPLACE INTO metric_definitions (id, code, name, subject_scope, scope_category, unit, formula, "
                    "definition, test_example) VALUES ((SELECT id FROM metric_definitions WHERE code=?),?,?,?,?,?,?,?,?)",
                    (m["code"], m["code"], m["name"], m["subject"], m.get("scope"), m.get("unit", ""),
                     m["formula"], m["definition"], m.get("test", "")))
    for k, v in DEFAULT_SETTINGS.items():
        cur.execute("INSERT OR IGNORE INTO settings (skey, svalue) VALUES (?,?)", (k, v))
    cur.execute("INSERT OR IGNORE INTO data_sources (id, name, source_type, permission_status, licence_notes) "
                "VALUES (1, 'Company live collection', 'live_collection', 'own_collection', "
                "'Events recorded by company staff attending the match.')")
    cur.execute("INSERT OR IGNORE INTO data_sources (id, name, source_type, permission_status, licence_notes) "
                "VALUES (2, 'Company video review', 'video_review', 'own_collection', "
                "'Events coded from permitted match video. Check video permission before client use.')")
