# Metric formulas and calculation tests

Every statistic is either a count of recorded events or one of the formulas below. Unknown or zero denominators return **N/A**; categories not collected return **Not collected**.

## Required formulas

```
Per 90              = Metric count / Minutes played x 90
Shot accuracy (%)   = Shots on target / Total shots x 100
Pass completion (%) = Completed passes / Passes attempted x 100
```

## Calculation tests

`tests/test_metrics.py` and the in-app page *Analysis → Metric definitions* run the formulas against hand-checked examples, for instance:

- Starter substituted off at 45' with 1 goal → minutes 45, goals per 90 = **2.0**
- 3 shots + 1 goal → 4 shots, 2 on target → shot accuracy **50.0%**
- 10 passes (8 completed) + 2 key passes → 12 attempted, 10 completed → **83.3%**
- Defensive events not collected → tackles = **Not collected** (not 0)
- Uncertain minutes → per-90 = **N/A**
- Zero shots → shot accuracy **N/A**
- Team goals include opponent own goals

## Metric catalogue

| Code | Name | Applies to | Needs category | Formula |
|---|---|---|---|---|
| `appearances` | Appearances | player | - | Count of matches where appearance status = 'played' |
| `minutes` | Minutes played | player | - | End minute - start minute (start = 0 for starters, or sub-on minute; end = earliest of sub-off, dismissal, full-time) |
| `goals` | Goals | player/team | goals | Count of recorded events matching the 'goals' rule (see event data dictionary) |
| `penalties_scored` | Penalties scored | player/team | goals | Count of recorded events matching the 'penalties_scored' rule (see event data dictionary) |
| `own_goals` | Own goals | player/team | goals | Count of recorded events matching the 'own_goals' rule (see event data dictionary) |
| `assists` | Assists | player/team | goals | Count of recorded events matching the 'assists' rule (see event data dictionary) |
| `goals_from_set_pieces` | Goals from set pieces | player/team | goals | Count of recorded events matching the 'goals_from_set_pieces' rule (see event data dictionary) |
| `assists_from_set_pieces` | Assists from set pieces | player/team | goals | Count of recorded events matching the 'assists_from_set_pieces' rule (see event data dictionary) |
| `shots` | Shots | player/team | shots | Count of recorded events matching the 'shots' rule (see event data dictionary) |
| `shots_on_target` | Shots on target | player/team | shots | Count of recorded events matching the 'shots_on_target' rule (see event data dictionary) |
| `passes_attempted` | Passes attempted | player/team | passes | Count of recorded events matching the 'passes_attempted' rule (see event data dictionary) |
| `passes_completed` | Passes completed | player/team | passes | Count of recorded events matching the 'passes_completed' rule (see event data dictionary) |
| `key_passes` | Key passes | player/team | passes | Count of recorded events matching the 'key_passes' rule (see event data dictionary) |
| `crosses` | Crosses | player/team | passes | Count of recorded events matching the 'crosses' rule (see event data dictionary) |
| `crosses_completed` | Crosses completed | player/team | passes | Count of recorded events matching the 'crosses_completed' rule (see event data dictionary) |
| `dribbles` | Dribbles / carries | player/team | attacking | Count of recorded events matching the 'dribbles' rule (see event data dictionary) |
| `offsides` | Offsides | player/team | attacking | Count of recorded events matching the 'offsides' rule (see event data dictionary) |
| `tackles` | Tackles | player/team | defensive | Count of recorded events matching the 'tackles' rule (see event data dictionary) |
| `tackles_won` | Tackles won | player/team | defensive | Count of recorded events matching the 'tackles_won' rule (see event data dictionary) |
| `interceptions` | Interceptions | player/team | defensive | Count of recorded events matching the 'interceptions' rule (see event data dictionary) |
| `clearances` | Clearances | player/team | defensive | Count of recorded events matching the 'clearances' rule (see event data dictionary) |
| `blocks` | Blocks | player/team | defensive | Count of recorded events matching the 'blocks' rule (see event data dictionary) |
| `recoveries` | Recoveries | player/team | defensive | Count of recorded events matching the 'recoveries' rule (see event data dictionary) |
| `duels` | Duels | player/team | defensive | Count of recorded events matching the 'duels' rule (see event data dictionary) |
| `duels_won` | Duels won | player/team | defensive | Count of recorded events matching the 'duels_won' rule (see event data dictionary) |
| `aerial_duels` | Aerial duels | player/team | defensive | Count of recorded events matching the 'aerial_duels' rule (see event data dictionary) |
| `aerial_duels_won` | Aerial duels won | player/team | defensive | Count of recorded events matching the 'aerial_duels_won' rule (see event data dictionary) |
| `saves` | Saves | player/team | defensive | Count of recorded events matching the 'saves' rule (see event data dictionary) |
| `fouls` | Fouls committed | player/team | discipline | Count of recorded events matching the 'fouls' rule (see event data dictionary) |
| `fouls_suffered` | Fouls suffered | player/team | discipline | Count of recorded events matching the 'fouls_suffered' rule (see event data dictionary) |
| `yellow_cards` | Yellow cards | player/team | discipline | Count of recorded events matching the 'yellow_cards' rule (see event data dictionary) |
| `red_cards` | Red cards | player/team | discipline | Count of recorded events matching the 'red_cards' rule (see event data dictionary) |
| `set_pieces_taken` | Set pieces taken | player/team | set_pieces | Count of recorded events matching the 'set_pieces_taken' rule (see event data dictionary) |
| `corners` | Corners | player/team | set_pieces | Count of recorded events matching the 'corners' rule (see event data dictionary) |
| `free_kicks` | Free kicks | player/team | set_pieces | Count of recorded events matching the 'free_kicks' rule (see event data dictionary) |
| `goals_per90` | Goals per 90 | player | goals | Per 90 = Metric count / Minutes played x 90 |
| `assists_per90` | Assists per 90 | player | goals | Per 90 = Metric count / Minutes played x 90 |
| `shots_per90` | Shots per 90 | player | shots | Per 90 = Metric count / Minutes played x 90 |
| `shots_on_target_per90` | Shots on target per 90 | player | shots | Per 90 = Metric count / Minutes played x 90 |
| `key_passes_per90` | Key passes per 90 | player | passes | Per 90 = Metric count / Minutes played x 90 |
| `passes_attempted_per90` | Passes attempted per 90 | player | passes | Per 90 = Metric count / Minutes played x 90 |
| `tackles_per90` | Tackles per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `interceptions_per90` | Interceptions per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `clearances_per90` | Clearances per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `blocks_per90` | Blocks per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `recoveries_per90` | Recoveries per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `duels_per90` | Duels per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `aerial_duels_per90` | Aerial duels per 90 | player | defensive | Per 90 = Metric count / Minutes played x 90 |
| `fouls_per90` | Fouls committed per 90 | player | discipline | Per 90 = Metric count / Minutes played x 90 |
| `shot_accuracy` | Shot accuracy (%) | player/team | shots | Shot accuracy (%) = Shots on target / Total shots x 100 |
| `pass_completion` | Pass completion (%) | player/team | passes | Pass completion (%) = Completed passes / Passes attempted x 100 |
| `possession` | Possession (%) | team | - | Reported only if a possession source is recorded for the match |