# Step 5 final outputs — club normalization completed

Generated: 2026-06-15

## Import-ready master-sheet files

1. `clubs_final_for_master.csv`
   - Import/replace the `clubs` sheet with this file.
   - Uses the master workbook's current 14-column schema.
   - Final canonical club rows: 464.

2. `player_club_at_callup_final_for_master.csv`
   - Import/replace the `player_club_at_callup` sheet with this file.
   - Uses the master workbook's current 12-column schema.
   - Final rows: 1248.

3. `squad_entries_final_for_master.csv`
   - Import/replace the `squad_entries` sheet with this file.
   - Uses the master workbook's current 14-column schema.
   - Final rows: 1248.
   - The Ali Yousif player_id repair is applied.
   - The final visible squad-entry spelling is corrected to Ali Yousif; the audit file preserves the ESPN/source spelling Ali Yousef.

## Audit/support files

- `clubs_final_with_audit_columns.csv`
  - Same final club rows but includes audit columns such as `player_count_at_callup` and `alias_count`.

- `player_club_at_callup_final_with_audit_columns.csv`
  - Same final player-club rows but includes original player/club ID and club-normalization audit columns.

- `squad_entries_final_with_audit_columns.csv`
  - Same final squad-entry rows but includes original player ID/name repair columns.

- `club_alias_map_step5_final.csv`
  - Maps old/raw club IDs and names to final canonical club IDs/names.
  - Includes the Hamburg/Hamburg SV -> Hamburger SV source-variant correction.
  - Includes Al-Khor -> Al-Karma SC as a source-error reassignment for Aymen Hussein, not as an alias merge.

- `club_review_queue_completed_resolved.csv`
  - Your completed review queue with final resolution fields added.
  - All candidate pairs remain separate.

- `player_club_source_corrections_step5.csv`
  - Row-level player-club corrections applied after your review.
  - Includes Lawrence Shankland, Aymen Hussein, Mohanad Ali, Sander Tangvik, and Luka Vuskovic.

- `club_name_changes_step5.csv`
  - Canonical club display-name changes applied from your review.

- `change_log_step5_final.csv`
  - Change-log entries matching the master workbook's `change_log` schema.
  - Can be appended to `change_log`.

- `step5_final_summary.csv`
  - Summary metrics and validation counts.

## Final validation

- `squad_entries_final_for_master.csv`: 1248 rows.
- `player_club_at_callup_final_for_master.csv`: 1248 rows.
- `clubs_final_for_master.csv`: 464 rows.
- Missing club IDs in final player-club table: 0.
- Duplicate player IDs in squad_entries: 0.
- Duplicate player IDs in player_club_at_callup: 0.

## Next step

Step 5 is now functionally complete. The next pipeline step should be Step 5b / Step 6 prep:
match final canonical clubs to Wikidata/official club sources, then geocode only these final canonical clubs.
