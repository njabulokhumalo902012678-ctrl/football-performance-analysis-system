# Employee roles and permissions matrix

Generated from `app/constants.py`. Access is controlled by role; an employee may hold more than one role (e.g. the *Data Collector* additional-duty role). Event recording is further restricted to matches the employee is **assigned** to.

| Permission | Managing Director | Operations Manager | Football Analyst | Video and Scouting Analyst | Technology Lead / Developer | Finance and Marketing Lead | Data Collector (additional duty) |
|---|---|---|---|---|---|---|---|
| `dashboard.executive` - View the company-wide executive dashboard | ✔ |  |  |  |  |  |  |
| `football.view` - View clubs, teams, players, competitions, seasons and venues | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `football.edit` - Create and edit football reference records |  | ✔ |  |  | ✔ |  |  |
| `match.view` - View fixtures and match status | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `match.manage` - Create fixtures, assign staff, manage match workflow and checklists |  | ✔ |  |  |  |  |  |
| `squad.edit` - Record squads, lineups and appearances for any match |  | ✔ |  |  |  |  |  |
| `events.collect` - Record match events (only for matches the user is assigned to) |  |  |  |  |  |  | ✔ |
| `events.view` - View recorded match events | ✔ | ✔ | ✔ | ✔ |  |  |  |
| `events.return` - Return submitted data for correction |  | ✔ | ✔ |  |  |  |  |
| `events.validate` - Validate and approve submitted match data |  |  | ✔ |  |  |  |  |
| `events.correct` - Correct submitted events (reason is mandatory and audited) |  |  | ✔ |  |  |  |  |
| `analysis.run` - Run the analysis engine and store analysis runs |  |  | ✔ |  |  |  |  |
| `analysis.view` - View statistics and analysis results | ✔ |  | ✔ | ✔ |  |  |  |
| `notes.edit` - Record analyst observations |  |  | ✔ | ✔ |  |  |  |
| `video.view` - View video assets and clips | ✔ |  | ✔ | ✔ |  |  |  |
| `video.manage` - Register video assets, create and tag clips |  |  |  | ✔ |  |  |  |
| `scouting.view` - View scouting reports | ✔ |  | ✔ | ✔ |  |  |  |
| `scouting.manage` - Create and edit scouting reports |  |  |  | ✔ |  |  |  |
| `report.create` - Create and edit report drafts and submit them for review |  |  | ✔ | ✔ |  |  |  |
| `report.view` - View internal reports | ✔ | ✔ | ✔ | ✔ |  | ✔ |  |
| `report.approve` - Approve or return reports for correction | ✔ |  |  |  |  |  |  |
| `report.share` - Share approved reports with clients and withdraw them | ✔ |  |  |  |  | ✔ |  |
| `clients.view` - View client records | ✔ |  |  |  |  | ✔ |  |
| `clients.manage` - Create and edit clients and client portal accounts |  |  |  |  |  | ✔ |  |
| `finance.summary` - View high-level financial summaries | ✔ |  |  |  |  | ✔ |  |
| `finance.view` - View detailed finance records | ✔ |  |  |  |  | ✔ |  |
| `finance.manage` - Create invoices, record payments and expenses |  |  |  |  |  | ✔ |  |
| `marketing.manage` - Manage leads, campaigns and contact history |  |  |  |  |  | ✔ |  |
| `tasks.own` - View and update own tasks | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `tasks.view_all` - View all tasks and departmental workload | ✔ | ✔ |  |  |  |  |  |
| `tasks.manage` - Create tasks and assign them to employees |  | ✔ |  |  |  |  |  |
| `audit.view` - View the audit log | ✔ |  |  |  | ✔ |  |  |
| `users.manage` - Manage user accounts, roles and activation |  |  |  |  | ✔ |  |  |
| `system.admin` - Backups, restores, error logs, imports and technical settings |  |  |  |  | ✔ |  |  |
| `settings.strategic` - Change strategic company settings | ✔ |  |  |  |  |  |  |
| `export.csv` - Export records to CSV/XLSX | ✔ | ✔ | ✔ |  | ✔ | ✔ |  |
| `import.data` - Import records from CSV |  |  |  |  | ✔ |  |  |

## Dashboards

- **Managing Director** → Executive Dashboard
- **Operations Manager** → Operations Dashboard
- **Football Analyst** → Analysis Dashboard
- **Video and Scouting Analyst** → Scouting Dashboard
- **Technology Lead / Developer** → Technical Administration Dashboard
- **Finance and Marketing Lead** → Business and Finance Dashboard
- **Data Collector (additional duty)** → My Collection Assignments

## Notable separations

- Technology Lead has **no** access to reports, finance or analysis editing: technical access does not grant permission to alter approved football analysis or financial records.
- Operations Manager can plan and assign but cannot validate or edit submitted/validated data; changes go through the correction process (reason required, audited).
- Only the Managing Director approves reports, and nobody can approve their own report.
- Finance records are visible only to roles holding `finance.view` / `finance.summary`.
- Clients (portal accounts) hold no employee permissions; they can only open reports shared with their own organisation.