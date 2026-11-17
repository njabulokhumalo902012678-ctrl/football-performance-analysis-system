"""Start the web application. For production use a WSGI server (see docs/DEPLOYMENT.md)."""
import os
from pathlib import Path

from app import create_app


def main():
    app = create_app()
    if not Path(app.config["DATABASE"]).exists():
        raise SystemExit("No database found. Run:  python manage.py demo   (fictional demo data)  or  python manage.py init-db")
    app.run(host=os.environ.get("FDPA_HOST", "127.0.0.1"), port=int(os.environ.get("FDPA_PORT", "5000")), debug=False)


if __name__ == "__main__":
    main()
