# User guide - all six positions (and clients)

Sign in at the web address your Technology Lead gives you. After sign-in you land on **your** dashboard. Click any dashboard number to open the matching list. The menu on the left shows only what your role may use (on a phone tap ☰). You are signed out automatically after 30 minutes of inactivity (adjustable). Change your password under *Change password* (10+ characters, upper + lower case + number).

## Match life cycle (everyone should know this)
Scheduled → Assigned → Ready for collection → Collection in progress → Data submitted → Validation required → (Corrections required ↩) → Data validated → Analysis in progress → Report under review → Approved → Delivered to client → Archived (plus Postponed / Cancelled).
Most later steps change automatically when someone does their job (e.g. submitting data, approving a report).

---
## 1. Managing Director - Executive Dashboard
* **Dashboard**: clubs/players/competitions, matches scheduled/completed/awaiting collection/awaiting validation, analyses in progress, reports awaiting approval/delivered, active clients, open requests, outstanding invoices, **staff workload and overdue tasks**, income/expenses this month, recent activity.
* **Approve reports**: *Reports* → open a report "Under review" → read the PDF → **Approve** or **Return** (reason required). You cannot approve a report you wrote.
* **Business view**: Finance overview, clients, tasks (all), audit log (*Administration → Audit log*).
* **Settings** (*Administration → Settings*): company name, confidentiality statement, **analyst rating rubric**, currency, invoice prefix, retention rule.
You do not need to enter match events - staff do that while you monitor progress.

## 2. Operations Manager - Operations Dashboard
1. **Create a fixture**: *New fixture* → competition, season, teams, kick-off, venue, deadline, client, and **assign** collector, backup collector, analyst, video/scouting analyst. A checklist and tasks are created automatically.
2. **Monitor**: dashboard shows *delayed collection*, *upcoming matches without a collector*, and a **data-completeness** table (lineups, events, scope, open errors).
3. **Lineups** (*Match → Lineups*): tick who is in the squad, starters, shirt, sub on/off minutes, sent-off minute. If a time is unknown tick **minutes uncertain** - never guess.
4. **Tasks**: create, assign, track (*Tasks*). Change status of fixtures in the planning stages on the match page.
5. After data is submitted you can **not** edit it - ask the analyst (correction process).

## 3. Football Analyst - Analysis Dashboard
1. **Validation queue** → open a match: see issues found automatically (score mismatch, duplicates, player not on pitch, missing lineups…), add your own issues, mark resolved, **Return to collector** (say what to fix) or **Approve for analysis** (blocked while errors remain).
2. **Correct events** (*Events / corrections*): *Edit* an event, give a **reason**; every correction is logged with before/after values.
3. **Analysis → Match analysis**: team and player tables, comparison chart, timeline, shot map (only when coordinates were collected). *Store analysis run* keeps a snapshot. Add **notes** (opinion) or **facts** (recorded fact).
4. **Advanced views**: on the match analysis page, heat maps and passing networks appear automatically when enough located actions / passes-with-receiver were collected (otherwise a note says why). Record the pitch location and *received by* for passes to get passing networks.
5. **Player view**: tick several matches to compare. Totals are marked * when categories differ between matches; trend charts appear only for consistent data.
6. **Reports → New player / match / team report**: choose match (and player), write observations, strengths, development areas, training priorities, recommendations (one point per line). Optional **rating 0-10 with justification** following the rubric. **Submit for review** creates a numbered version + PDF. After return, edit and resubmit (new version).

## 4. Video and Scouting Analyst - Scouting Dashboard
* **Video library → Register video**: reference link or upload (stored in protected storage). Record **permission status** and source/licence. Footage can only be *client-shareable* when permission = permitted. Not-permitted footage cannot be streamed or clipped.
* **Clips**: add start/end seconds, event type, player, tags, notes.
* **Scouting records**: separate **recorded facts** from **opinion** fields; link the matches observed (sample size is the number linked; *High* confidence needs ≥3 matches). Submit for review → Managing Director approves. Then *Reports → New scouting report* makes the PDF.

## 5. Technology Lead - Technical Administration Dashboard
See `ADMIN_GUIDE.md`: users and roles, settings, backups and restore test, error log, imports, audit, exports. You cannot view reports or finance by design.

## 6. Finance and Marketing Lead - Business and Finance Dashboard
* **Clients**: register (club, academy, player, coach, agent, tournament organiser, other), record services, status, follow-ups, contact history; **create portal accounts** (temporary password shown once).
* **Prospects/leads and campaigns**: status pipeline, follow-up dates, convert a prospect to a client.
* **Finance**: services & prices, proposals, **invoices** (auto numbering, lines, tax, due date) → *Mark as sent* → *Record payment* (overpayment refused; status updates to partial/paid) · overdue flags · expense register with receipt reference · cash-flow by month · costs per match.
* **Share reports**: approved reports → *Delivery → Share with client*. Track viewed/downloaded. **Withdraw** an incorrect report (reason required); the analyst corrects and reissues.
* **Client requests/feedback**: *Client requests* → respond.

## Data Collector (additional duty any employee can hold) - phone
1. *My assignments* → open the match. Check **Lineups** exist and the **collection scope** is ticked (what you will record).
2. For each event: tap **team → event → player**, choose outcome (and related player / set piece), set period & minute, optional tap on the pitch for location, **Save as draft**. Minute and period are remembered for the next event.
3. If it looks like a duplicate you are asked to confirm. Errors show in red. **If the connection drops, the event is kept on your phone** (a yellow banner counts them) and syncs automatically when you are back online - or tap *Sync now*. Do not clear the browser's data while events are waiting.
4. No signal? Record on paper or in a spreadsheet; **download the CSV template**, fill it, upload later (all-or-nothing, errors listed by row).
5. At full time enter the **official score** (Match page) and **Submit for validation**. After submission only an analyst can change events.

## Clients - Client portal
Sign in; see only reports shared with your organisation, open/download PDFs, see delivery dates, send requests or feedback, view your agreed services. You cannot see internal notes, other clients or finance.
