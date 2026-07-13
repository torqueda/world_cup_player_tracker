# Step 5 Club Normalization Outputs

This bundle starts Step 5 for the 2026 FIFA World Cup player-club map. It uses the latest `players` sheet from the master workbook plus the Step 2 `clubs.csv`, `player_club_at_callup.csv`, and `squad_entries.csv`.

## Output files

- `pre_step5_audit.csv`: quick integrity checks before club normalization.
- `clubs_normalized.csv`: canonical club table after high-confidence name-variant merges. Club metadata/QIDs/geocoding fields are intentionally blank where not yet verified.
- `player_club_at_callup_club_normalized.csv`: call-up club join table with normalized `club_id` values and the Ali Yousef/Yousif `player_id` repair.
- `club_alias_map.csv`: audit table mapping every old Step 2 club row to its canonical club row.
- `club_normalization_review_queue.csv`: possible duplicate/name-collision cases that were not auto-merged.
- `club_normalization_summary.csv`: row counts and normalization metrics.
- `squad_entries_id_repaired.csv`: same squad entries as the Step 2 input, but with the Ali Yousef/Yousif `player_id` repair so joins match the current players sheet.
- `normalize_clubs_step5.py`: dependency-free reproducibility helper. It expects CSV inputs, including a current `players.csv` export.

## Current pass summary

- Old Step 2 club rows: 511
- Normalized canonical club rows: 463
- Canonical-club reduction: 48
- Curated auto-merge groups applied: 45
- Manual review queue rows: 18

## Important notes

- No geocoding was performed. That should wait until club normalization is approved.
- Wikidata QIDs for clubs were not filled in this pass because the uploaded Step 2 club file had blank QID fields.
- The review queue should be checked before replacing the master `clubs` and `player_club_at_callup` sheets.
