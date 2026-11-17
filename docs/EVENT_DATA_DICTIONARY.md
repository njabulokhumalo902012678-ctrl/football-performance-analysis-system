# Football event data dictionary

Generated from `app/constants.py`; the list of event types is configurable in the `event_types` table.

## Fields recorded for every event

| Field | Meaning |
|---|---|
| match_id, team_id | Match and the team performing the event. Must be one of the two teams in the match. |
| player_id | Main player (must be in the match lineup and on the correct team). Optional for period events. |
| event_type | See table below. |
| period, minute, second | `1H`, `2H`, `ET1`, `ET2`, `PS`; minute 0-150, second optional. |
| outcome | Allowed values depend on the event type. |
| related_player_id | Assist provider, receiver, player coming on, fouled player, etc. |
| x_start, y_start, x_end, y_end | Pitch coordinates 0-100, **recorded from the point of view of the team in possession attacking left to right**. Optional. |
| set_piece_type | corner, free_kick, throw_in, goal_kick, other (goals, shots, clearances, aerial duels). |
| video_timestamp | Seconds into the linked video, optional. |
| collector_id, source_id | Who recorded it and the data source (with licence/permission). |
| validation_status | draft → submitted → validated (or returned). |
| correction_reason, modified_by | Set when an event is corrected after submission. |

## Event types

| Code | Name | Category | Scope category | Outcomes | Related player | Coordinates | Set piece |
|---|---|---|---|---|---|---|---|
| `shot` | Shot | attacking | shots | on_target, off_target, blocked | - | start | yes |
| `goal` | Goal | attacking | goals | - | Assisted by | start | yes |
| `assist` | Assist | attacking | goals | - | Goal scored by | none | - |
| `key_pass` | Key pass | attacking | passes | - | Shot taken by | start_end | - |
| `pass` | Pass | attacking | passes | completed, incomplete | Received by | start_end | - |
| `cross` | Cross | attacking | passes | completed, incomplete | Received by | start_end | - |
| `dribble` | Dribble or carry | attacking | attacking | successful, unsuccessful | - | start_end | - |
| `corner` | Corner | attacking | set_pieces | - | - | start | - |
| `free_kick` | Free kick | attacking | set_pieces | - | - | start | - |
| `penalty` | Penalty | attacking | goals | scored, saved, missed | - | start | - |
| `offside` | Offside | attacking | attacking | - | - | none | - |
| `tackle` | Tackle | defensive | defensive | won, lost | - | start | - |
| `interception` | Interception | defensive | defensive | - | - | start | - |
| `clearance` | Clearance | defensive | defensive | - | - | start | yes |
| `block` | Block | defensive | defensive | - | - | start | - |
| `recovery` | Recovery | defensive | defensive | - | - | start | - |
| `duel` | Duel | defensive | defensive | won, lost | - | start | - |
| `aerial_duel` | Aerial duel | defensive | defensive | won, lost | - | start | yes |
| `foul` | Foul | defensive | discipline | committed, suffered | Fouled player | start | - |
| `card` | Card | defensive | discipline | yellow, second_yellow, red | - | none | - |
| `goalkeeper_action` | Goalkeeper action | defensive | defensive | save, claim, punch, distribution, sweeper | - | start | - |
| `substitution` | Substitution | admin | admin | - | Player coming on | none | - |
| `period_start` | Period start | admin | admin | - | - | none | - |
| `period_end` | Period end | admin | admin | - | - | none | - |
| `own_goal` | Own goal | admin | goals | - | - | none | - |
| `other` | Other event | admin | admin | - | - | none | - |

## Collection scope (what "Not collected" means)

For every match the collector declares which categories were collected. A statistic from a category that was **not** declared is displayed as **Not collected**, never as 0.

| Category | Covers |
|---|---|
| `goals` | Goals, assists and own goals |
| `shots` | Shots and shots on target |
| `passes` | Passes, key passes and crosses |
| `attacking` | Dribbles and offsides |
| `defensive` | Tackles, interceptions, clearances, blocks, recoveries, duels, goalkeeper actions |
| `discipline` | Fouls and cards |
| `set_pieces` | Corners and free kicks |

## Counting conventions (important for consistent data)

1. **Goal**: record once as a `goal` event (assist = *related player*) or as a `penalty` event with outcome `scored`. Do not also record a `shot`. Goals count as shots on target.
2. **Assist**: preferred method is the related player on the goal. A separate `assist` event is also counted - never record both for the same goal (the validator warns).
3. **Own goal**: record against the team of the player who scored it; the goal is credited to the opponent.
4. **Key pass** counts as a completed pass. **Crosses** are counted separately from passes.
5. **Second yellow card** (`second_yellow`) counts as one yellow and one red card.
6. **Free kicks and corners** record the taker; a shot from a free kick is *also* recorded as a `shot` with set piece = free_kick.
7. **Substitutions**: minutes come from the lineup/appearance record (sub-on/off minutes); the `substitution` event is informational for the timeline.
8. **Possession** is never calculated from events. It is stored only with a documented source/method on the match record.