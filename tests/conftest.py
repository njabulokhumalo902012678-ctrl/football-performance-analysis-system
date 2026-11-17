import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def demo_app(tmp_path_factory):
    """A complete fictional demo system in a temporary folder (real workflow executed through the app)."""
    d = tmp_path_factory.mktemp("fdpa")
    os.environ["FDPA_DB"] = str(d / "test.sqlite3")
    from app import create_app, db as database, demo
    app = create_app({"TESTING": False, "REPORT_DIR": str(d / "reports"), "VIDEO_DIR": str(d / "videos"),
                      "BACKUP_DIR": str(d / "backups"), "OUTBOX_DIR": str(d / "outbox")})
    for k in ("REPORT_DIR", "VIDEO_DIR", "BACKUP_DIR", "OUTBOX_DIR"):
        Path(app.config[k]).mkdir(parents=True, exist_ok=True)
    database.init_db(d / "test.sqlite3")
    ids = demo.build(d / "test.sqlite3")
    demo.run_workflow(app, ids)
    app.ids = ids
    return app


def login(app, user, pw="Demo#2026pass"):
    c = app.test_client()
    c.get("/login")
    with c.session_transaction() as s:
        s["_csrf"] = "t"
    r = c.post("/login", data={"identifier": user, "password": pw, "_csrf": "t"})
    assert r.status_code == 302, f"{user} could not sign in"
    return c


def post(c, url, **data):
    with c.session_transaction() as s:
        s["_csrf"] = "t"
    data["_csrf"] = "t"
    return c.post(url, data=data)
