# Acceptance tests (specification section 21)

Run `python -m pytest tests -q` (all must pass). Last run in the build environment: **34 passed, 0 failed**
(the tests build a complete fictional system, then drive it through the real application).

| # | Requirement | Test(s) |
|---|---|---|
| 1 | Six positions sign in and reach their dashboard | `test_each_position_gets_its_dashboard` (x6) |
| 2 | Unauthorised actions blocked | `test_unauthorised_actions_are_blocked`, `test_csrf_is_enforced`, `test_login_lockout_and_password_policy`, `test_session_timeout` |
| 3 | Ops creates a match and assigns a collector | `test_ops_creates_match_and_assigns_collector` |
| 4 | Collector records and submits events (phone API + CSV fallback) | `test_full_collection_flow_on_new_match`, `test_csv_fallback_import` |
| 5 | Analyst validates | `test_full_collection_flow_on_new_match`, `test_validation_blocks_approval_with_errors` |
| 6 | Corrections recorded in audit history | `test_collect_validate_correct_and_audit` |
| 7 | Minutes and statistics correct on test data | `test_player_minutes_and_missing_data`, `tests/test_metrics.py` |
| 8 | Missing information never shown as zero | `test_missing_data_is_never_shown_as_zero`, `test_player_minutes_and_missing_data` |
| 9 | Player performance PDF | `test_reports_pdf_and_review_flow` |
| 10 | Match report PDF | `test_reports_pdf_and_review_flow` |
| 11 | Review, approve, share to correct client | `test_reports_pdf_and_review_flow`, `test_client_isolation`, `test_withdrawn_report_disappears_for_client` |
| 12 | One client cannot open another's report | `test_client_isolation` |
| 13 | Invoices and expenses | `test_invoices_and_balances` |
| 14 | MD sees company-wide summaries | `test_md_cannot_see_detailed_finance_without_permission_but_sees_summary`, dashboard tests |
| 15 | CSV export | `test_csv_export_and_formula_injection_guard` |
| 16 | Backup restores successfully | `test_backup_and_restore` |
| 17 | Clear errors, technical errors recorded | `test_errors_are_friendly_and_logged`, `test_every_screen_renders_for_every_role` (asserts zero logged errors across ~60 screens x 7 roles) |
| - | Video permission rules | `test_video_sharing_rules` |
| P8 | Heat maps / passing networks only from collected data; offline queue present | `test_advanced_charts_only_from_collected_data`, `test_collection_page_has_offline_queue` |

Manual checks still recommended before go-live: a pilot match recorded on a real Android phone; printing a PDF; restoring a backup onto a clean machine; a security review of the hosting setup.
