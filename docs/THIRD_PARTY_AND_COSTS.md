# Third-party libraries, data sources, permissions and ongoing costs

| Component | Purpose | Licence | Cost |
|---|---|---|---|
| Python 3.11+ | runtime | PSF licence | free |
| Flask (+ Werkzeug, Jinja2, MarkupSafe, itsdangerous, click) | web framework, password hashing | BSD-3 | free |
| SQLite (bundled with Python) | database | public domain | free |
| ReportLab (open-source edition) | PDF reports | BSD | free |
| Matplotlib | charts, shot maps, diagram | PSF-based (matplotlib licence) | free |
| pandas, NumPy | data handling / analytics | BSD-3 | free |
| openpyxl | XLSX handling | MIT | free |
| pytest (development only) | tests | MIT | free |
| Optional: waitress / Caddy / Nginx / XAMPP Apache | production serving, HTTPS | ZPL / Apache-2 / BSD | free |
| Optional: MySQL / MariaDB | alternative database | GPL | free |

Check the licences of the exact library versions installed (`pip-licenses`) before commercial distribution.

## Football data and video permissions
* All demo data is **fictional**. No real player or club data, logos, crests or photographs are included.
* The system records the **source and permission/licence** for every data source and video asset. Do not republish third-party data or footage commercially without written permission.
* No licensed data feeds are used. **xG, GPS/tracking and other advanced metrics are not produced** (they need licensed data or a validated model).

## Ongoing costs (estimates - verify locally)
| Item | Typical range |
|---|---|
| Domain name | USD 10-20 / year |
| Small cloud VM (1 vCPU, 2 GB) | USD 5-12 / month |
| Off-site backup storage (50 GB) | USD 1-5 / month |
| TLS certificate (Let's Encrypt/Caddy) | free |
| Email sending (optional SMTP) | free tier - USD 10 / month |
| Video storage | depends on volume (~USD 2-5 / 100 GB / month) |
| Licensed data (optional, future) | quote-based, can be substantial |
| Developer time for updates/security patches | allow ~1-2 days / quarter |
