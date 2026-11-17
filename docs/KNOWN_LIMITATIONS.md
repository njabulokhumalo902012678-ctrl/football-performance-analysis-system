# Known limitations and planned improvements

## Limitations (honest list)
1. **Technology stack differs from the recommended PHP/MySQL** (Python/Flask/SQLite - see README). A MySQL schema is provided but was not run against MySQL; migrating the data layer is estimated at 2-4 days (`DEPLOYMENT.md`).
2. SQLite suits a small team (a few simultaneous users). Heavy concurrent match-day load or many collectors saving at once should move to MySQL/PostgreSQL.
3. **Offline collection is partial.** If the connection drops while the collection page is open, new events are kept in the phone's browser storage and synced automatically when it is back online (a banner shows how many are waiting). The page itself cannot be *loaded* without a connection (no service worker/installed app), corrections cannot be queued, and clearing browser data loses queued events. Fallback = paper/CSV upload.
4. **Advanced analytics (Phase 8) - partly built.** Built: shot maps, **heat maps** (≥15 located actions per team, ≥8 per player) and **passing networks** (completed passes with a start location and a recorded receiver), on the analysis screen and in reports - only when the data exists. **Not built, deliberately:** expected goals (xG), progression maps, GPS/sprint/physical workload - these need licensed data, tracking sensors or a validated model; inventing them would break the "no false statistics" rule. Possession is only shown from a documented source.
5. Client-facing sharing is through the portal; there is no automatic email notification to clients (password-reset email works with SMTP configured; otherwise written to `instance/outbox`).
6. Video: files are streamed with the browser player; there is no server-side clip cutting/transcoding - clips are timestamp tags. Large uploads are limited by the web server settings.
7. Player profile images are not uploaded (flag only); club/competition logos are not stored.
8. PDF reports use Arial (Windows), DejaVu or Liberation Sans if found on the machine, so accented/extended Latin and many scripts print correctly; if none is found they fall back to Helvetica (Western European only).
9. The report layout is automatic (panels flow onto extra pages). Visual design follows the supplied sample reports in style but is not pixel-identical; stats shown in the samples that need unsupported data (xG, touches in box, big chances, progressive passes, possession without source) are intentionally omitted.
10. Two-factor authentication and single sign-on are not included.
11. Tested in this build with Python 3.12 and a simulated browser client (automated tests); not yet exercised on physical Android/iOS devices or with real stadium connectivity - do a pilot match before relying on it.
12. Appearance minutes assume the scheduled match length from the fixture (default 90); for extra time set 120.

## Planned improvements
Full offline-first collection (service worker / installable app), MySQL migration, progression maps and a validated xG model (needs data/licence), email notifications, PDF font embedding, club logos, season-level player reports, report templates per client, role-permission editor in the UI, 2FA.
