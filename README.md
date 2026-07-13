# World Cup 2026 Player Tracker

This repository is building a structured dataset and eventual interactive dashboard for the 2026 FIFA World Cup. The project tracks players, national teams, clubs at call-up, club geolocation, source metadata, and change history so the data can power a public-facing map and analytics site later on.

## Current Phase

The dataset is final-roster verified and tournament-ready: all 48 final squads cross-checked against FIFA's lists (with cut players kept as `removed` and late replacements ingested and Wikidata-enriched), official player/team statistics and all match results through the quarterfinals, plus coaches and match officials. The site has grown into a seven-route dashboard (Overview, Players & Clubs, National Teams, Matches, Stats, Insights, Data & Sources). The remaining push is the pre-semifinal deploy: replicate local workbook fixes into the Google Sheets master, refresh stats after the semifinals if desired, and pick the hosting target (see `docs/roadmap_to_deployment.md`).

## Running The Prototype Locally

The prototype lives in `site/` and reads directly from `data/processed/app_exports/` through Vite's `@data` alias, so no separate data setup is needed — just install and run.

**Prerequisites:**
- Node.js 20 or later (developed and tested with Node 26)
- [pnpm](https://pnpm.io) — the project pins `pnpm@11.7.0` via `packageManager` in `site/package.json`. If you don't already have pnpm, either run `corepack enable` (Node ships `corepack`) or `npm install -g pnpm`.

**Steps:**

```bash
cd site
pnpm install
pnpm dev
```

Then open the URL Vite prints (defaults to `http://localhost:5173`) in a browser. The dev server supports hot reload, so edits under `site/src/` show up immediately.

**Other useful commands, run from `site/`:**

- `pnpm build` — type-checks (`tsc --noEmit`) and then produces a production build in `site/dist/`
- `pnpm typecheck` — type-checks only, no build
- `pnpm preview` — serves the last production build locally, to sanity-check the built output

If the dataset changes (`data/processed/app_exports/*.json` regenerated from the master workbook), just refresh the dev server — no rebuild step is required to pick up new data while `pnpm dev` is running.

## Repository Layout

```text
.
|-- data/
|   |-- raw/                               # Original roster scrape outputs and source HTML
|   |-- master/                            # Current workbook snapshot from Google Sheets
|   `-- processed/
|       |-- stable_ids_initial/            # Historical initial relational exports
|       |-- player_wikidata_matching/      # Player Wikidata matching outputs
|       |-- image_metadata/                # Commons image metadata outputs
|       |-- identity_validation/           # Read-only player QA outputs
|       |-- club_normalization_working/    # Historical Step 5 working files
|       |-- club_normalization_final/      # Historical Step 5 final files
|       |-- club_id_reconciliation/        # Historical club-ID reconciliation outputs
|       |-- club_geolocation_baseline/     # Canonical club baseline and city geocoding workfiles
|       |-- club_geolocation_outdated/     # Older Step 6 / hybrid artifacts kept for provenance
|       |-- master_exports/                # Current workbook-backed CSV snapshots and audits
|       `-- app_exports/                   # Current app-ready JSON exports
|-- scripts/
|   |-- data_ingestion/
|   |-- data_pipeline/
|   |-- image_collection/
|   |-- validation/
|   `-- geolocation/
|-- scripts/export/                        # Workbook sync, audit, and app-export scripts
|-- site/                                  # React + TypeScript + React Router + Vite prototype
|-- docs/                                  # Status docs, handoff, and current-work checklist
`-- archive/local_artifacts/               # Local temp/cache artifacts, not pipeline inputs
```

## Data Model

The master workbook is treated like a small relational database:

- `players`: one row per player, keyed by `player_id`
- `squad_entries`: one row per player’s 2026 World Cup squad inclusion
- `clubs`: one row per canonical club
- `player_club_at_callup`: join table connecting players to clubs
- `sources`: source registry
- `change_log`: tracked corrections and changes
- `manual_review_queue`: review items that still need to be brought forward if desired
- `world_cup_history`: future expansion sheet

Stable internal IDs are the join keys. Do not replace them with external IDs such as Wikidata QIDs.

## Current Source Of Truth

- Master workbook: `data/master/world_cup_2026_player_map_master.xlsx`
- Canonical club baseline: `data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv`
- Final city geocoding workfile: `data/processed/club_geolocation_baseline/club_city_geocoding_workfile.csv`
- Current workbook-backed CSV snapshots: `data/processed/master_exports/`
- Current app-ready JSON exports: `data/processed/app_exports/`
- Current build checklist: `docs/current_work_dashboard_prototype_checklist.md`
- Deferred follow-ups list: `docs/deferred_dataset_and_prototype_todo.md`
- Roadmap to the deployed v1: `docs/roadmap_to_deployment.md`
- Launch guide (hosting decision, costs, exact steps): `docs/launch_guide.md`
- How to publish it for non-technical users (hosting, costs, steps): `docs/launch_guide.md`

## Current Status

1. Data collection and cleanup phases (roster ingestion, stable IDs, Wikidata matching, club normalization, city geolocation) are complete.
2. The dataset is final-roster verified (2026-07-12/13):
   - all 48 squads cross-checked against FIFA's final lists — 1,221 confirmed, 27 cut (`squad_status=removed`), 27 late replacements ingested with generated IDs and Wikidata-enriched birthplaces;
   - `clubs` holds `461` canonical clubs collapsing to `397` geocoded city rows;
   - official FIFA stats (goals/assists/minutes/cards/goalkeeping) for all 1,231 registered players, team stats with computed W/D/L and stage reached, and all 104 matches;
   - coaches (48) and match officials (167) collected with sources registered.
3. The export pipeline (`refresh_all_exports.py`) regenerates everything from the workbook in one command with a strict integrity audit.
4. The site (`site/`, React + TypeScript + Vite) is a seven-route dashboard:
   - `Players & Clubs`: country-bubble world map that reveals city dots on zoom/selection, cascading filters with removable chips, club/player autocomplete, auto-zoom to filtered regions;
   - `National Teams`: sortable rosters with coach, captain, caps, and stage reached;
   - `Matches`: all results grouped by stage (and by group within the group stage) plus the remaining schedule;
   - `Stats`: pictogram leaderboards (Golden Boot, assists, minutes, saves, Fair Play) and a sortable team table;
   - `Insights`: home-grown-vs-diaspora donuts for all 48 squads with sorting, birthplace charts with hover detail, squad-age list, club/league rankings, and a team-explorer sidebar;
   - `Data & Sources`: statement-style attributions, change log, and method notes;
   - plus a live-metric `Overview`.
5. Remaining before deploy: replicate local workbook fixes to the Google Sheets master, optionally refresh stats after the semifinals, and execute the hosting decision (`docs/roadmap_to_deployment.md`).

## Important Notes

- For current work, build from the master workbook, `data/processed/master_exports/`, or `data/processed/app_exports/`.
- Historical step-specific folders may still contain older pre-reconciliation club IDs such as the former PSG duplicate. Keep them for provenance, but do not treat them as the current app source.
- A lightweight audit file now exists at `data/processed/master_exports/master_workbook_alignment_summary.json`.
- Possible player birthplace naming follow-ups are intentionally separated into `data/processed/master_exports/player_birthplace_city_candidate_review.csv` instead of being auto-applied.

## Running The Data Pipeline

Python dependencies are pinned in `requirements.txt` and installed in the project virtualenv:

```bash
python3 -m venv .venv          # once, if .venv does not exist yet
.venv/bin/pip install -r requirements.txt
```

To refresh everything from the master workbook in one command (CSV snapshots → strict integrity audit → app-ready JSON):

```bash
.venv/bin/python scripts/export/refresh_all_exports.py
```

The audit step runs with `--strict`, so the pipeline stops before writing app JSON if any integrity check fails (duplicate player IDs, club-ID joins missing, club-baseline drift, or lingering old club IDs).

## Current Scripts

Export pipeline:

- `scripts/export/refresh_all_exports.py`: runs the three scripts below in order, stopping on any failure
- `scripts/export/export_master_workbook_to_csv.py`: writes current workbook-backed CSV snapshots
- `scripts/export/audit_master_workbook_alignment.py`: verifies current club IDs and club-baseline alignment (`--strict` exits non-zero on failed checks; clubs pending geocoding are reported, not failed)
- `scripts/export/export_master_workbook_to_json.py`: creates app-ready JSON exports (players, clubs, cities, teams, matches, player/team stats, coaches, referees, sources, change log)

Tournament-data collection and reconciliation (July 2026 finalization run):

- `scripts/data_ingestion/scrape_wikipedia_squads.py`: final 26-man squads, shirt numbers, coaches, replacement notes (re-runnable; archives the HTML snapshot)
- `scripts/data_ingestion/scrape_wikipedia_officials.py`: referees, assistants, and VARs with match assignments
- `scripts/data_pipeline/reconcile_final_rosters.py`: diffs scraped final squads against the dataset (confirmed / cut / new players)
- `scripts/data_pipeline/build_workbook_import_sheets.py`: merges all collected data into import-ready workbook sheets
- `scripts/data_pipeline/apply_post_import_fixes.py` and `scripts/data_pipeline/enrich_new_players_from_wikidata.py`: post-import corrections and Wikidata birthplace enrichment, applied to the local xlsx with backups plus replication CSVs for Google Sheets
- `scripts/geolocation/build_city_country_lookup_from_clubs.py`: deduplicates club cities
- `scripts/geolocation/build_city_geocoding_workfile.py`: builds the city-level geocoding workfile
- `scripts/geolocation/apply_city_geocoding_results.py`: reapplies reviewed city geocoding decisions

## Next Step

Launch. The delivery decision is made and documented in `docs/launch_guide.md`: the site
ships as a free static website (Netlify or Cloudflare Pages), not a downloadable program.
The remaining launch blockers are listed at the top of
`docs/current_work_dashboard_prototype_checklist.md` — in short: sync the local workbook
fixes back to the Google Sheets master, make the first git commit and push to GitHub,
connect the host (~15 minutes), and smoke-test the live URL. After the tournament ends,
one final data refresh locks the dataset.
