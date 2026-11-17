# Implementation plan, screen designs and phase status

*(Specification section 23 asks for the database diagram, screen designs, role matrix and plan first.)*
Database diagram → `DATABASE_DIAGRAM.md`, `database_diagram.png` · Role matrix → `ROLES_PERMISSIONS_MATRIX.md`.

## Architecture
Browser (laptop / Android phone, responsive HTML/CSS/JS, no inline scripts) → Flask application (`app/views/*` blueprints = screens and business rules) → data layer (`app/db.py`, parameterised SQL) → SQLite (`app/schema.sql`; MySQL version in `mysql/`).
Separate modules: analysis engine (`metrics.py`), validation/workflow (`workflow.py`), report rendering (`pdfgen.py`, `charts.py`) - the PDF renderer works only from a stored snapshot so report versions never change.
Analytics access: the engine reads only validated events/appearances through the application; there is no separate high-privilege database connection.

## Screen designs (what each screen shows)
| Screen | Who | Content |
|---|---|---|
| Login / reset | all | username or email + password, lockout message, reset by email link |
| Dashboard | each role | KPI tiles (clickable) + role panels (see user guide) |
| Football records (clubs, teams, players, competitions, seasons, venues, data sources) | Ops, Tech, view for others | list with search/filter/export, add/edit forms, player profile with team history, season teams |
| Fixtures | Ops (create), others view | list with status filters and "deadline missed" flags; form with assignments; match page with scope, official result, checklist, status history |
| Lineups | Ops, collector, validators | per team table: squad, starter, shirt, position, sub on/off, sent off, status, minutes uncertain |
| Event collection (mobile) | collector | team pills → event buttons → player buttons → outcome → minute/period → optional pitch tap → save draft; recent events; submit; CSV fallback |
| Validation queue / review | analyst | issues list, lineups, events, return/approve |
| Match analysis, player analysis, metric definitions | analysts, scouts, MD | stat tables ("Not collected"/"N/A"), charts, notes, runs, formula self-test |
| Reports list/detail | analyst, scout, MD, finance | inputs, rating rubric, versions, PDF preview, review decision, delivery tracking |
| Video library, clips, scouting records | scout | permission status, protected playback, tagged clips, facts vs opinion |
| Clients, leads, campaigns, requests | finance, MD (view) | records, contact history, portal accounts |
| Finance | finance, MD (view) | overview, invoices, payments, expenses, proposals, services |
| Tasks | all | own tasks; managers/MD see all + workload |
| Administration | tech, MD | users, roles matrix, settings, audit, backups, errors, imports |
| Client portal | clients | reports, PDFs, profile, requests/feedback, agreed services |

Report layouts (PDF, A4 landscape) follow the supplied samples: navy header with logo/name/tagline, panel grid, mirrored comparison bars, timeline, shot map - see `sample_data/*.pdf`.

## Phase status
| Phase | Scope | Status |
|---|---|---|
| 1 Foundation | database, login, accounts, 6 roles, permissions, settings, dashboards | ✔ done |
| 2 Football records | clubs…venues, fixtures, squads, appearances | ✔ done |
| 3 Match data collection | mobile form, assignments, drafts, CSV fallback, validation, correction + approval | ✔ done |
| 4 Analysis engine | metric definitions, player/team/match stats, per-90, data-quality checks, real-data charts | ✔ done |
| 5 Reports | player, match, team, scouting reports; PDF; review/approval; client sharing; versions; withdraw | ✔ done |
| 6 Company operations | clients, tasks, finance, marketing, invoices, expenses, management dashboard | ✔ done |
| 7 Security & deployment | backup + restore test, access-control tests, error logging, production notes, documentation | ✔ done (automation = scheduled command, see guide) |
| 8 Advanced | heat maps, passing networks, xG, advanced scouting, video workflow | ◐ **partly done**: coordinate shot maps ✔, heat maps ✔, passing networks ✔, phone-side offline queue ✔, video clip tagging/permissions ✔. **Not done (needs licensed data / validated model):** xG, progression maps, GPS/physical metrics |

## Suggested rollout
1. Install on one machine, create real accounts, load clubs/teams/players you are authorised to hold.
2. Pilot one match: lineups → collect → submit → validate → report (use a second person as validator).
3. Fix process gaps; then roll out to all matches; schedule backups; add HTTPS hosting before remote collectors use mobile data.
