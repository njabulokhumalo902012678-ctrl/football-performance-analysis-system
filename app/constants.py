"""Static configuration shared across the application: roles, permissions, workflow statuses, event types."""

COMPANY_NAME = "Football Data and Performance Analysis Company"
COMPANY_TAGLINE = "Data | Analysis | Opportunities"

# --------------------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------------------
PERMISSIONS = {
    "dashboard.executive": "View the company-wide executive dashboard",
    "football.view": "View clubs, teams, players, competitions, seasons and venues",
    "football.edit": "Create and edit football reference records",
    "match.view": "View fixtures and match status",
    "match.manage": "Create fixtures, assign staff, manage match workflow and checklists",
    "squad.edit": "Record squads, lineups and appearances for any match",
    "events.collect": "Record match events (only for matches the user is assigned to)",
    "events.view": "View recorded match events",
    "events.return": "Return submitted data for correction",
    "events.validate": "Validate and approve submitted match data",
    "events.correct": "Correct submitted events (reason is mandatory and audited)",
    "analysis.run": "Run the analysis engine and store analysis runs",
    "analysis.view": "View statistics and analysis results",
    "notes.edit": "Record analyst observations",
    "video.view": "View video assets and clips",
    "video.manage": "Register video assets, create and tag clips",
    "scouting.view": "View scouting reports",
    "scouting.manage": "Create and edit scouting reports",
    "report.create": "Create and edit report drafts and submit them for review",
    "report.view": "View internal reports",
    "report.approve": "Approve or return reports for correction",
    "report.share": "Share approved reports with clients and withdraw them",
    "clients.view": "View client records",
    "clients.manage": "Create and edit clients and client portal accounts",
    "finance.summary": "View high-level financial summaries",
    "finance.view": "View detailed finance records",
    "finance.manage": "Create invoices, record payments and expenses",
    "marketing.manage": "Manage leads, campaigns and contact history",
    "tasks.own": "View and update own tasks",
    "tasks.view_all": "View all tasks and departmental workload",
    "tasks.manage": "Create tasks and assign them to employees",
    "audit.view": "View the audit log",
    "users.manage": "Manage user accounts, roles and activation",
    "system.admin": "Backups, restores, error logs, imports and technical settings",
    "settings.strategic": "Change strategic company settings",
    "export.csv": "Export records to CSV/XLSX",
    "import.data": "Import records from CSV",
}

ROLES = {
    "managing_director": dict(
        name="Managing Director", dashboard_title="Executive Dashboard", primary=1,
        description="Leadership and overall company management.",
        perms=["dashboard.executive", "football.view", "match.view", "events.view", "analysis.view",
               "scouting.view", "video.view", "report.view", "report.approve", "report.share",
               "clients.view", "finance.summary", "finance.view", "tasks.own", "tasks.view_all",
               "audit.view", "settings.strategic", "export.csv"]),
    "operations_manager": dict(
        name="Operations Manager", dashboard_title="Operations Dashboard", primary=1,
        description="Plans and coordinates football data collection and operations.",
        perms=["football.view", "football.edit", "match.view", "match.manage", "squad.edit", "events.view",
               "events.return", "tasks.own", "tasks.view_all", "tasks.manage", "export.csv", "report.view"]),
    "football_analyst": dict(
        name="Football Analyst", dashboard_title="Analysis Dashboard", primary=1,
        description="Validates data and analyses match, team and player performance.",
        perms=["football.view", "match.view", "events.view", "events.return", "events.validate",
               "events.correct", "analysis.run", "analysis.view", "notes.edit", "report.create",
               "report.view", "video.view", "scouting.view", "tasks.own", "export.csv"]),
    "video_scouting_analyst": dict(
        name="Video and Scouting Analyst", dashboard_title="Scouting Dashboard", primary=1,
        description="Video review, player observation and scouting reports.",
        perms=["football.view", "match.view", "events.view", "analysis.view", "notes.edit", "video.view",
               "video.manage", "scouting.view", "scouting.manage", "report.create", "report.view",
               "tasks.own"]),
    "technology_lead": dict(
        name="Technology Lead / Developer", dashboard_title="Technical Administration Dashboard", primary=1,
        description="Develops, maintains and secures the company's technology systems.",
        perms=["football.view", "football.edit", "match.view", "users.manage", "system.admin", "import.data",
               "export.csv", "audit.view", "tasks.own"]),
    "finance_marketing_lead": dict(
        name="Finance and Marketing Lead", dashboard_title="Business and Finance Dashboard", primary=1,
        description="Commercial activities, financial records and marketing.",
        perms=["football.view", "match.view", "clients.view", "clients.manage", "finance.summary",
               "finance.view", "finance.manage", "marketing.manage", "report.view", "report.share",
               "tasks.own", "export.csv"]),
    # Additional-duty role: management can give any employee collection duties.
    "data_collector": dict(
        name="Data Collector (additional duty)", dashboard_title="My Collection Assignments", primary=0,
        description="Records match events for matches the employee is assigned to.",
        perms=["football.view", "match.view", "events.collect", "tasks.own"]),
    # Client portal role (never granted to employees).
    "client": dict(
        name="Client", dashboard_title="Client Portal", primary=0,
        description="External client account: sees only reports shared with the client's organisation.",
        perms=[]),
}
PRIMARY_ROLE_ORDER = ["managing_director", "operations_manager", "football_analyst",
                      "video_scouting_analyst", "technology_lead", "finance_marketing_lead", "data_collector"]

# --------------------------------------------------------------------------------------
# Match workflow
# --------------------------------------------------------------------------------------
MATCH_STATUSES = [
    ("scheduled", "Scheduled"), ("assigned", "Assigned"), ("ready_for_collection", "Ready for collection"),
    ("collection_in_progress", "Collection in progress"), ("data_submitted", "Data submitted"),
    ("validation_required", "Validation required"), ("corrections_required", "Corrections required"),
    ("data_validated", "Data validated"), ("analysis_in_progress", "Analysis in progress"),
    ("report_under_review", "Report under review"), ("approved", "Approved"),
    ("delivered_to_client", "Delivered to client"), ("archived", "Archived"),
    ("postponed", "Postponed"), ("cancelled", "Cancelled"),
]
STATUS_LABEL = dict(MATCH_STATUSES)
PRE_SUBMISSION = {"scheduled", "assigned", "ready_for_collection", "collection_in_progress", "corrections_required"}
VALIDATED_OR_LATER = {"data_validated", "analysis_in_progress", "report_under_review", "approved",
                      "delivered_to_client", "archived"}
MANUAL_STATUSES = ["scheduled", "assigned", "ready_for_collection", "postponed", "cancelled", "archived"]

# --------------------------------------------------------------------------------------
# Data collection
# --------------------------------------------------------------------------------------
SCOPE_CATEGORIES = [
    ("goals", "Goals, assists and own goals"),
    ("shots", "Shots and shots on target"),
    ("passes", "Passes, key passes and crosses"),
    ("attacking", "Dribbles and offsides"),
    ("defensive", "Tackles, interceptions, clearances, blocks, recoveries, duels, goalkeeper actions"),
    ("discipline", "Fouls and cards"),
    ("set_pieces", "Corners and free kicks"),
]
PERIODS = [("1H", "1st half"), ("2H", "2nd half"), ("ET1", "Extra time 1"), ("ET2", "Extra time 2"), ("PS", "Shoot-out")]
SET_PIECE_TYPES = ["corner", "free_kick", "throw_in", "goal_kick", "other"]

# code, name, category, scope, outcomes, needs_player, related_label, coords, uses_set_piece, sort
EVENT_TYPES = [
    ("shot", "Shot", "attacking", "shots", "on_target,off_target,blocked", 1, None, "start", 1, 10),
    ("goal", "Goal", "attacking", "goals", "", 1, "Assisted by", "start", 1, 11),
    ("assist", "Assist", "attacking", "goals", "", 1, "Goal scored by", "none", 0, 12),
    ("key_pass", "Key pass", "attacking", "passes", "", 1, "Shot taken by", "start_end", 0, 13),
    ("pass", "Pass", "attacking", "passes", "completed,incomplete", 1, "Received by", "start_end", 0, 14),
    ("cross", "Cross", "attacking", "passes", "completed,incomplete", 1, "Received by", "start_end", 0, 15),
    ("dribble", "Dribble or carry", "attacking", "attacking", "successful,unsuccessful", 1, None, "start_end", 0, 16),
    ("corner", "Corner", "attacking", "set_pieces", "", 1, None, "start", 0, 17),
    ("free_kick", "Free kick", "attacking", "set_pieces", "", 1, None, "start", 0, 18),
    ("penalty", "Penalty", "attacking", "goals", "scored,saved,missed", 1, None, "start", 0, 19),
    ("offside", "Offside", "attacking", "attacking", "", 1, None, "none", 0, 20),
    ("tackle", "Tackle", "defensive", "defensive", "won,lost", 1, None, "start", 0, 30),
    ("interception", "Interception", "defensive", "defensive", "", 1, None, "start", 0, 31),
    ("clearance", "Clearance", "defensive", "defensive", "", 1, None, "start", 1, 32),
    ("block", "Block", "defensive", "defensive", "", 1, None, "start", 0, 33),
    ("recovery", "Recovery", "defensive", "defensive", "", 1, None, "start", 0, 34),
    ("duel", "Duel", "defensive", "defensive", "won,lost", 1, None, "start", 0, 35),
    ("aerial_duel", "Aerial duel", "defensive", "defensive", "won,lost", 1, None, "start", 1, 36),
    ("foul", "Foul", "defensive", "discipline", "committed,suffered", 1, "Fouled player", "start", 0, 37),
    ("card", "Card", "defensive", "discipline", "yellow,second_yellow,red", 1, None, "none", 0, 38),
    ("goalkeeper_action", "Goalkeeper action", "defensive", "defensive", "save,claim,punch,distribution,sweeper", 1, None, "start", 0, 39),
    ("substitution", "Substitution", "admin", "admin", "", 1, "Player coming on", "none", 0, 50),
    ("period_start", "Period start", "admin", "admin", "", 0, None, "none", 0, 51),
    ("period_end", "Period end", "admin", "admin", "", 0, None, "none", 0, 52),
    ("own_goal", "Own goal", "admin", "goals", "", 1, None, "none", 0, 53),
    ("other", "Other event", "admin", "admin", "", 0, None, "none", 0, 60),
]

NEEDS_PERIOD_MINUTE = True

# --------------------------------------------------------------------------------------
# Misc dropdown values
# --------------------------------------------------------------------------------------
CLIENT_TYPES = ["Football club", "Academy", "Individual player", "Coach", "Agent", "Tournament organiser", "Other football organisation"]
AGREEMENT_STATUSES = ["prospect", "proposal_sent", "agreed", "active", "paused", "ended"]
LEAD_STATUSES = ["new", "contacted", "meeting_booked", "proposal_sent", "won", "lost"]
VERIFICATION = ["unverified", "partly_verified", "verified"]
POSITIONS = ["Goalkeeper", "Centre Back", "Right Back", "Left Back", "Defensive Midfielder", "Central Midfielder",
             "Attacking Midfielder", "Right Winger", "Left Winger", "Second Striker", "Striker"]
PRIORITIES = ["low", "normal", "high", "urgent"]
DEPARTMENTS = ["Management", "Operations", "Analysis", "Scouting", "Technology", "Finance and Marketing"]
TASK_STATUSES = ["open", "in_progress", "blocked", "done", "cancelled"]
EXPENSE_CATEGORIES = ["Transport", "Equipment", "Software and hosting", "Data and licences", "Marketing",
                      "Salaries and fees", "Office", "Other"]
CONFIDENCE_LEVELS = ["low", "medium", "high"]
VIDEO_PERMISSIONS = ["pending", "permitted", "restricted", "not_permitted"]
VIDEO_CATEGORIES = ["goal", "shot", "pass", "tackle", "interception", "defensive_action", "dribble", "set_piece", "positioning", "other"]
