#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
[ -f instance/fdpa.sqlite3 ] || python manage.py demo
echo "Done. Start with: . .venv/bin/activate && python run.py"
