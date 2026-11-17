# Setup on Windows (and where XAMPP fits)

## Do I need XAMPP?
**Not to run this system.** It is a Python application with a built-in SQLite database, so it needs only Python.
XAMPP (Apache + MySQL) becomes useful later if you (a) move the database to MySQL, or (b) put Apache in front of the app as a web server with HTTPS. Both are described in `DEPLOYMENT.md`.

## Steps
1. **Install Python 3.11+** (python.org → Downloads). In the installer tick **"Add python.exe to PATH"**.
2. Copy this folder to the laptop, e.g. `C:\fdpa`.
3. Double-click **`setup.bat`**. It creates `.venv`, installs `Flask, ReportLab, Matplotlib, pandas, NumPy, openpyxl` and builds the demo database.
4. Double-click **`run.bat`**; open **http://127.0.0.1:5000**.
5. Sign in with a demo account (see README). Explore each role.

## Using it from a phone (match collection)
1. Laptop and phone on the same Wi-Fi. Find the laptop address: `ipconfig` → "IPv4 Address", e.g. `192.168.1.20`.
2. In a command prompt before starting: `set FDPA_HOST=0.0.0.0` then `run.bat` (Windows Firewall will ask - allow *private networks* only).
3. On the phone browse to `http://192.168.1.20:5000`. For real match days host the system on a server with HTTPS (see `DEPLOYMENT.md`) so collectors can use mobile data.

## Starting with real data
```
del instance\fdpa.sqlite3          (removes the demo database)
.venv\Scripts\python manage.py init-db     (creates an empty database and your Technology Lead account)
```
Then create the other employee accounts in **Administration → Users**. Enter only real client/player data you are authorised to hold.

## Python analytics environment
The analysis engine (`app/metrics.py`) uses plain Python; `pandas`, `numpy` and `matplotlib` are installed for CSV/XLSX handling and charts. The analytics code reads only validated match events through the application's own queries - it never uses administrative database credentials and has no separate connection. To work on analytics separately: `.venv\Scripts\activate`, `python manage.py selftest` (runs the formula tests), `python -m pytest tests`.

## Version control
`git init` in the folder; a `.gitignore` is included (excludes the database, backups, secrets). Host the repository in a **private company-owned** account.
