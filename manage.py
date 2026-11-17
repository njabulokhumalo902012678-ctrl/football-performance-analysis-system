#!/usr/bin/env python3
"""Management commands:  python manage.py <command>

  init-db        create an EMPTY database with roles/permissions and one Technology Lead account
  demo           create a database filled with FICTIONAL demonstration data (replaces nothing; refuses if a database exists)
  run            start the web application (development server)
  backup         create a backup zip in ./backups
  restore FILE   restore a backup zip over the live database (the app must be stopped)
  test-restore   verify the newest backup in a scratch folder
  selftest       run the metric formula self-tests
"""
import getpass
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app import create_app, db as database  # noqa: E402
from app.security import hash_password, password_problems  # noqa: E402


def db_path():
    return Path(os.environ.get("FDPA_DB", ROOT / "instance" / "fdpa.sqlite3"))


def cmd_init():
    p = db_path()
    database.init_db(p)
    print(f"Created empty database at {p}")
    username = input("Technology Lead username [tech]: ").strip() or "tech"
    email = input("Email: ").strip()
    name = input("Full name: ").strip()
    while True:
        pw = getpass.getpass("Password (10+ chars, upper, lower, number): ")
        probs = password_problems(pw)
        if probs:
            print("Password needs:", ", ".join(probs))
            continue
        if pw != getpass.getpass("Repeat password: "):
            print("Passwords do not match.")
            continue
        break
    con = sqlite3.connect(p)
    uid = con.execute("INSERT INTO users (username,email,full_name,password_hash) VALUES (?,?,?,?)", (username.lower(), email.lower(), name, hash_password(pw))).lastrowid
    con.execute("INSERT INTO user_roles SELECT ?, id FROM roles WHERE code IN ('technology_lead')", (uid,))
    con.commit()
    con.close()
    print("Done. Sign in, then create the other employee accounts under Administration > Users.")


def cmd_demo():
    from app import demo
    p = db_path()
    database.init_db(p)
    ids = demo.build(p)
    app = create_app()
    demo.run_workflow(app, ids)
    print(f"Demo database created at {p}")
    print("Sign in as: md, ops, analyst, scout, tech, finance, collector, client.rudimentary, client.city")
    print(f"Password for all demo accounts: {demo.DEMO_PASSWORD}")


def cmd_backup():
    app = create_app()
    with app.app_context():
        from app.views.admin import make_backup
        print("Backup written:", make_backup())


def cmd_restore(f):
    zp = Path(f)
    if not zp.exists():
        sys.exit("Backup file not found.")
    p = db_path()
    if input(f"This REPLACES {p} with the backup. The app must be stopped. Type YES to continue: ") != "YES":
        sys.exit("Cancelled.")
    tmp = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(zp) as z:
        z.extract("fdpa.sqlite3", tmp)
        con = sqlite3.connect(tmp / "fdpa.sqlite3")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            sys.exit("Backup failed the integrity check - nothing was changed.")
        con.close()
        if p.exists():
            shutil.copy2(p, str(p) + ".before_restore")
        shutil.copy2(tmp / "fdpa.sqlite3", p)
        rdir = ROOT / "instance" / "reports"
        rdir.mkdir(parents=True, exist_ok=True)
        for n in z.namelist():
            if n.startswith("reports/") and n.endswith(".pdf"):
                with z.open(n) as src, open(rdir / Path(n).name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print("Restore complete. Previous database kept as", str(p) + ".before_restore")


def cmd_test_restore():
    app = create_app()
    with app.app_context():
        from app.views.admin import test_restore
        files = sorted((ROOT / "backups").glob("fdpa_backup_*.zip"))
        if not files:
            sys.exit("No backups found.")
        ok, integrity, diffs = test_restore(files[-1])
        print(files[-1].name, "->", "OK" if ok else "FAILED", integrity, diffs or "")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c = sys.argv[1]
    if c == "init-db":
        cmd_init()
    elif c == "demo":
        cmd_demo()
    elif c == "run":
        import run
        run.main()
    elif c == "backup":
        cmd_backup()
    elif c == "restore" and len(sys.argv) > 2:
        cmd_restore(sys.argv[2])
    elif c == "test-restore":
        cmd_test_restore()
    elif c == "selftest":
        from app.metrics import run_selftests
        res = run_selftests()
        for n, ok, d in res:
            print("PASS" if ok else "FAIL", n, "" if ok else d)
        sys.exit(0 if all(r[1] for r in res) else 1)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
