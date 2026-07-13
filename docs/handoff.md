# Project Handoff

## Overview

This project is building a structured World Cup dataset first and an interactive browser-based dashboard second. The immediate goal is no longer to finish raw club geolocation discovery from scratch; it is to treat the current workbook-backed dataset as the working baseline and start building the first prototype safely on top of it.

## Confirmed Current State

- Master workbook: `data/master/world_cup_2026_player_map_master.xlsx`
- Current canonical clubs: `456`
- Current unique geocoded club cities: `393`
- Current players: `1,248`
- Current national teams in `squad_entries`: `48`
- Current source of truth for app work:
  - workbook itself
  - `data/processed/master_exports/`
  - `data/processed/app_exports/`

### Verified during the latest sync

- `clubs` in the workbook matches `data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv` on canonical text fields.
- Every current `player_club_at_callup.club_id` resolves to a current club row.
- No current workbook rows still use the old PSG duplicate club ID.
- The workbook `clubs` sheet already contains the city-geodata fields needed for the dashboard.
- `data/processed/app_exports/` has been regenerated directly from the current workbook.

## What Has Been Done So Far

1. Roster ingestion
   - ESPN roster article scraped and corrected.
   - Output basis lives in `data/raw/`.

2. Stable internal IDs
   - Player, club, squad-entry, and player-club IDs were generated.
   - Historical initial outputs live in `data/processed/stable_ids_initial/`.

3. Player enrichment
   - Wikidata matching, manual review, image metadata enrichment, and read-only identity validation were completed.
   - Outputs live in `data/processed/player_wikidata_matching/`, `data/processed/image_metadata/`, and `data/processed/identity_validation/`.

4. Club normalization
   - Canonical club naming and deduplication were completed.
   - Historical step outputs remain in `data/processed/club_normalization_working/` and `data/processed/club_normalization_final/`.

5. Club geolocation
   - The project pivoted to a city-level geocoding workflow.
   - Canonical current files now live in `data/processed/club_geolocation_baseline/`.
   - Final city geocoding decisions have already been propagated into the workbook `clubs` sheet.

6. Current-source export layer
   - `scripts/export/export_master_workbook_to_csv.py` now writes current workbook-backed CSV snapshots to `data/processed/master_exports/`.
   - `scripts/export/audit_master_workbook_alignment.py` writes:
     - `data/processed/master_exports/master_workbook_alignment_summary.json`
     - `data/processed/master_exports/player_birthplace_city_candidate_review.csv`
   - `scripts/export/export_master_workbook_to_json.py` writes current app-ready JSON to `data/processed/app_exports/`.

## What We Are Doing Now

We are in the transition from data cleanup to application prototyping.

### Current objective

Build the first frontend prototype against stable JSON exports without losing track of data provenance or accidentally pulling from stale historical files.

### Current working assumptions

- The current `players`, `clubs`, `squad_entries`, and `player_club_at_callup` workbook sheets are the working baseline.
- `club_name`, `club_name_ascii`, `league`, `country`, `city`, `stadium`, and city geodata in the workbook `clubs` sheet are canonical for the prototype.
- Potential player birthplace naming alignment should be reviewed deliberately, not auto-normalized wholesale.

## Important Caveat

Older historical files are still preserved and may intentionally contain outdated IDs or intermediate states. That is acceptable for provenance. It does mean:

- do not use `stable_ids_initial/`, `club_normalization_final/`, or similar historical folders as the app source
- do use `data/processed/master_exports/` or `data/processed/app_exports/` for current work

## Remaining Data-Side Follow-Ups

These are not blockers for scaffolding the app, but they are still worth tracking:

1. Decide whether to normalize the two birthplace naming candidates in `player_birthplace_city_candidate_review.csv`:
   - `New York City` vs `New York`
   - `Tashkent Region` vs `Tashkent`
2. Decide whether to import historical manual-review provenance into the workbook `manual_review_queue`.
3. Decide whether `world_cup_history` is needed for the first prototype or later.
4. Decide how to expose `change_log` and source transparency in the UI.
5. Keep deferred dataset and provenance items tracked in `docs/deferred_dataset_and_prototype_todo.md`.

## Next Workstream

The next workstream is the React + TypeScript + React Router + Vite prototype.

Use this order:

1. Read `README.md`
2. Read `docs/current_work_dashboard_prototype_checklist.md`
3. Use `data/processed/app_exports/` as the frontend data source
4. Scaffold the app shell
5. Implement the first route with real data before broadening the UI

## If Someone Picks This Up Cold

Start here:

1. `README.md`
2. `docs/current_work_dashboard_prototype_checklist.md`
3. `data/processed/master_exports/master_workbook_alignment_summary.json`
4. `data/processed/app_exports/meta.json`

That sequence gives the current status, current source-of-truth files, and the immediate roadmap without forcing anyone back through outdated Step 6 notes first.
