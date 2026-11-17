"""Generate documentation that must always match the code: ER diagram, roles matrix, event dictionary, metric formulas.
Run:  python tools/make_docs.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import constants as C  # noqa: E402
from app.metrics import METRICS, NAMES  # noqa: E402

DOCS = ROOT / "docs"
sql = (ROOT / "app" / "schema.sql").read_text(encoding="utf-8")

# ------------------------------------------------------------------ parse schema
tables, fks = {}, []
for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.S):
    name, body = m.group(1), m.group(2)
    cols = []
    for line in body.split("\n"):
        line = line.strip().rstrip(",")
        fm = re.match(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", line)
        if fm:
            fks.append((name, fm.group(1), fm.group(2)))
        elif line and not line.startswith(("PRIMARY KEY", "UNIQUE", "--")):
            cols.append(line.split()[0])
    tables[name] = cols

GROUPS = {
    "Users and security": ["settings", "roles", "permissions", "role_permissions", "users", "user_roles", "password_resets", "audit_logs", "error_logs"],
    "Clients and commercial": ["clients", "client_users", "leads", "contact_history", "marketing_campaigns", "services", "proposals", "invoices", "invoice_items", "payments", "expenses", "client_requests"],
    "Football records": ["clubs", "teams", "players", "player_team_history", "competitions", "seasons", "competition_teams", "venues", "matches", "match_status_history", "match_checklist_items", "match_squads", "appearances", "collection_assignments", "match_collection_scope"],
    "Data collection": ["data_sources", "event_types", "match_events", "validation_issues", "import_jobs"],
    "Analysis and scouting": ["metric_definitions", "analysis_runs", "metric_values", "analyst_notes", "video_assets", "video_clips", "scouting_reports", "scouting_report_matches"],
    "Reports and workflow": ["reports", "report_versions", "report_shares", "tasks", "backup_logs"],
}

# ------------------------------------------------------------------ ER diagram markdown (mermaid)
lines = ["# Database relationship diagram", "",
         f"{len(tables)} tables, {len(fks)} foreign-key relationships. Generated from `app/schema.sql` by `tools/make_docs.py`.", "",
         "The image `database_diagram.png` shows all tables by domain. The Mermaid diagrams below render in GitHub, VS Code and most Markdown viewers.", "",
         "Key relationships from the specification: a **match** belongs to a **competition** and **season**, involves two **teams** (home and away), "
         "has many **appearances** and **match_events**, can produce multiple **analysis_runs** and **reports**; a report has many **report_versions** and **report_shares** to clients.", ""]
for g, members in GROUPS.items():
    lines += [f"## {g}", "", "```mermaid", "erDiagram"]
    for t in members:
        lines.append(f"  {t} {{")
        for c in tables[t][:9]:
            lines.append(f"    string {c}")
        lines.append("  }")
    for (t, col, ref) in fks:
        if t in members and ref in members:
            lines.append(f"  {ref} ||--o{{ {t} : \"{col}\"")
    lines += ["```", ""]
lines += ["## All foreign keys", "", "| Table | Column | References |", "|---|---|---|"] + [f"| {t} | {c} | {r} |" for t, c, r in fks]
(DOCS / "DATABASE_DIAGRAM.md").write_text("\n".join(lines), encoding="utf-8")

# ------------------------------------------------------------------ ER image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

colors = ["#0b2a55", "#1f9d3a", "#2f6fd0", "#b8530b", "#6a3fa0", "#0f7d8a"]
fig, ax = plt.subplots(figsize=(24, 15))
ax.set_xlim(0, 24)
ax.set_ylim(0, 15)
ax.axis("off")
pos = {}
layout = {"Users and security": (0.3, 14.5, 3), "Clients and commercial": (11.0, 14.5, 4), "Football records": (0.3, 9.6, 5),
          "Data collection": (17.3, 9.6, 2), "Analysis and scouting": (0.3, 3.9, 4), "Reports and workflow": (13.0, 3.9, 3)}
bw, bh = 2.55, 0.52
for (g, members), colr in zip(GROUPS.items(), colors):
    x0, y0, cols_n = layout[g]
    ax.text(x0, y0 + 0.15, g.upper(), fontsize=12, fontweight="bold", color=colr)
    for i, t in enumerate(members):
        cx = x0 + (i % cols_n) * (bw + 0.35) + (2.0 if g == "Football records" and False else 0)
        cy = y0 - 0.7 - (i // cols_n) * 0.85
        pos[t] = (cx + bw / 2, cy + bh / 2)
        ax.add_patch(FancyBboxPatch((cx, cy), bw, bh, boxstyle="round,pad=0.02", fc="white", ec=colr, lw=1.6, zorder=3))
        ax.text(cx + bw / 2, cy + bh / 2, t, ha="center", va="center", fontsize=8.5, zorder=4, color="#111")
for (t, col, ref) in fks:
    if t in pos and ref in pos and t != ref and ref != "users":
        (x1, y1), (x2, y2) = pos[t], pos[ref]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color="#5b6b85", lw=0.8, alpha=0.6, shrinkA=14, shrinkB=14, mutation_scale=9), zorder=1)
ax.text(12, 0.2, "Arrows point from the child table (foreign key) to the parent table. Links to users (created_by, user_id, recorded_by) are omitted for clarity - see DATABASE_DIAGRAM.md.  Football Data and Performance Analysis Company - database relationships",
        ha="center", fontsize=10, color="#333")
fig.savefig(DOCS / "database_diagram.png", dpi=110, bbox_inches="tight", facecolor="white")

# ------------------------------------------------------------------ roles matrix
roles = [(k, v) for k, v in C.ROLES.items() if k != "client"]
md = ["# Employee roles and permissions matrix", "", "Generated from `app/constants.py`. Access is controlled by role; an employee may hold more than one role "
      "(e.g. the *Data Collector* additional-duty role). Event recording is further restricted to matches the employee is **assigned** to.", "",
      "| Permission | " + " | ".join(v["name"] for _, v in roles) + " |", "|---|" + "---|" * len(roles)]
for p, desc in C.PERMISSIONS.items():
    md.append(f"| `{p}` - {desc} | " + " | ".join("✔" if p in v["perms"] else "" for _, v in roles) + " |")
md += ["", "## Dashboards", ""] + [f"- **{v['name']}** → {v['dashboard_title']}" for _, v in roles]
md += ["", "## Notable separations", "",
       "- Technology Lead has **no** access to reports, finance or analysis editing: technical access does not grant permission to alter approved football analysis or financial records.",
       "- Operations Manager can plan and assign but cannot validate or edit submitted/validated data; changes go through the correction process (reason required, audited).",
       "- Only the Managing Director approves reports, and nobody can approve their own report.",
       "- Finance records are visible only to roles holding `finance.view` / `finance.summary`.",
       "- Clients (portal accounts) hold no employee permissions; they can only open reports shared with their own organisation."]
(DOCS / "ROLES_PERMISSIONS_MATRIX.md").write_text("\n".join(md), encoding="utf-8")

# ------------------------------------------------------------------ event dictionary
ev = ["# Football event data dictionary", "", "Generated from `app/constants.py`; the list of event types is configurable in the `event_types` table.", "",
      "## Fields recorded for every event", "",
      "| Field | Meaning |", "|---|---|",
      "| match_id, team_id | Match and the team performing the event. Must be one of the two teams in the match. |",
      "| player_id | Main player (must be in the match lineup and on the correct team). Optional for period events. |",
      "| event_type | See table below. |", "| period, minute, second | `1H`, `2H`, `ET1`, `ET2`, `PS`; minute 0-150, second optional. |",
      "| outcome | Allowed values depend on the event type. |", "| related_player_id | Assist provider, receiver, player coming on, fouled player, etc. |",
      "| x_start, y_start, x_end, y_end | Pitch coordinates 0-100, **recorded from the point of view of the team in possession attacking left to right**. Optional. |",
      "| set_piece_type | corner, free_kick, throw_in, goal_kick, other (goals, shots, clearances, aerial duels). |",
      "| video_timestamp | Seconds into the linked video, optional. |", "| collector_id, source_id | Who recorded it and the data source (with licence/permission). |",
      "| validation_status | draft → submitted → validated (or returned). |", "| correction_reason, modified_by | Set when an event is corrected after submission. |", "",
      "## Event types", "", "| Code | Name | Category | Scope category | Outcomes | Related player | Coordinates | Set piece |", "|---|---|---|---|---|---|---|---|"]
for (code, name, cat, scope, outcomes, np_, rel, coords, sp, _s) in C.EVENT_TYPES:
    ev.append(f"| `{code}` | {name} | {cat} | {scope} | {outcomes.replace(',', ', ') or '-'} | {rel or '-'} | {coords} | {'yes' if sp else '-'} |")
ev += ["", "## Collection scope (what \"Not collected\" means)", "",
       "For every match the collector declares which categories were collected. A statistic from a category that was **not** declared is displayed as **Not collected**, never as 0.", "",
       "| Category | Covers |", "|---|---|"] + [f"| `{k}` | {v} |" for k, v in C.SCOPE_CATEGORIES]
ev += ["", "## Counting conventions (important for consistent data)", "",
       "1. **Goal**: record once as a `goal` event (assist = *related player*) or as a `penalty` event with outcome `scored`. Do not also record a `shot`. Goals count as shots on target.",
       "2. **Assist**: preferred method is the related player on the goal. A separate `assist` event is also counted - never record both for the same goal (the validator warns).",
       "3. **Own goal**: record against the team of the player who scored it; the goal is credited to the opponent.",
       "4. **Key pass** counts as a completed pass. **Crosses** are counted separately from passes.",
       "5. **Second yellow card** (`second_yellow`) counts as one yellow and one red card.",
       "6. **Free kicks and corners** record the taker; a shot from a free kick is *also* recorded as a `shot` with set piece = free_kick.",
       "7. **Substitutions**: minutes come from the lineup/appearance record (sub-on/off minutes); the `substitution` event is informational for the timeline.",
       "8. **Possession** is never calculated from events. It is stored only with a documented source/method on the match record."]
(DOCS / "EVENT_DATA_DICTIONARY.md").write_text("\n".join(ev), encoding="utf-8")

# ------------------------------------------------------------------ metrics doc
mt = ["# Metric formulas and calculation tests", "",
      "Every statistic is either a count of recorded events or one of the formulas below. Unknown or zero denominators return **N/A**; categories not collected return **Not collected**.", "",
      "## Required formulas", "", "```", "Per 90              = Metric count / Minutes played x 90",
      "Shot accuracy (%)   = Shots on target / Total shots x 100", "Pass completion (%) = Completed passes / Passes attempted x 100", "```", "",
      "## Calculation tests", "",
      "`tests/test_metrics.py` and the in-app page *Analysis → Metric definitions* run the formulas against hand-checked examples, for instance:", "",
      "- Starter substituted off at 45' with 1 goal → minutes 45, goals per 90 = **2.0**", "- 3 shots + 1 goal → 4 shots, 2 on target → shot accuracy **50.0%**",
      "- 10 passes (8 completed) + 2 key passes → 12 attempted, 10 completed → **83.3%**", "- Defensive events not collected → tackles = **Not collected** (not 0)",
      "- Uncertain minutes → per-90 = **N/A**", "- Zero shots → shot accuracy **N/A**", "- Team goals include opponent own goals", "",
      "## Metric catalogue", "", "| Code | Name | Applies to | Needs category | Formula |", "|---|---|---|---|---|"]
for m in METRICS:
    mt.append(f"| `{m['code']}` | {m['name']} | {m['subject']} | {m.get('scope') or '-'} | {m['formula']} |")
(DOCS / "METRICS.md").write_text("\n".join(mt), encoding="utf-8")
print("docs generated")
