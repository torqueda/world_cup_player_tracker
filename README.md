# World Cup 2026 Player Tracker

This repository holds a structured dataset of the 2026 FIFA World Cup and the public site built on it, https://worldcupplayertracker.netlify.app/. The dataset tracks players, national teams, clubs at call-up, club locations, matches, statistics, coaches, match officials, sources, and change history.

## Current State

The dataset is final. All 48 final squads were cross-checked against FIFA's lists: cut players are kept as `removed`, and the 27 late replacements were added and matched to Wikidata. Official player and team statistics and all 104 results run through the final on 2026-07-19; the last refresh was on 2026-08-19. **The version-controlled workbook `data/master/world_cup_2026_player_map_master.xlsx` is the canonical master list**; the Google Sheets copy was retired on 2026-07-13.

The site has seven pages: Home, Club Map, Squads, Matches, Leaders, Analysis, and Methodology. Netlify builds the site and deploys `main`. The repository is public at https://github.com/torqueda/world_cup_player_tracker.

## Running The Site Locally

The site lives in `site/` and reads `data/processed/app_exports/` directly through Vite's `@data` alias, so there is no separate data setup: install and run.

**Prerequisites:**
- Node.js 24 or later (the pinned pnpm 11.x requires Node 22.13+; CI uses Node 24)
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
- `pnpm test` — compiles and runs the TypeScript unit tests for shared analytical selectors
- `pnpm typecheck` — type-checks only, no build
- `pnpm preview` — serves the last production build locally, to sanity-check the built output

If the dataset changes (`data/processed/app_exports/*.json` regenerated from the master workbook), just refresh the dev server — no rebuild step is required to pick up new data while `pnpm dev` is running.

## Analytical Layer

The `Analysis` route now uses shared selectors in `site/src/lib/analytics/` instead of embedding calculations directly in JSX. Those selectors are documented, typed, deterministic, and covered by unit tests. The UI states the definition, population, thresholds, and export timestamp for derived charts and tables, and offers CSV downloads for the squad scorecard and club/league impact tables.

Current derived metrics include:

- Squad composition: average and median age as of `2026-06-11`, under-23 and age-30-plus counts, total and median pre-tournament caps, domestic-club share, clubs/countries/leagues represented, birthplace home-grown share, and stage reached.
- Club and league impact: players sent, teams represented, tournament minutes, goals, assists, goal contributions, and players with meaningful minutes. The optional impact index is a published weighted formula, not an official ranking.
- Concentration and diversity: largest-club share, largest-club-country share, club HHI, club-country HHI, effective clubs, and normalized effective clubs. Higher HHI means concentration in fewer clubs.
- Team comparison: shareable `teamA` and `teamB` query parameters compare roster profile, experience, domestic/foreign mix, club diversity, record, goals, xG, and top performers.
- Player efficiency: goals, assists, goal contributions, and cards per 90, with an adjustable minimum-minutes threshold and separate goalkeeper/outfield views.
- Match and venue analysis: goals per match by stage and venue, score-margin distribution, draws, penalty shootouts, team records by stage, and confederation-vs-confederation results.
- Data quality dashboard: row counts, active-player image coverage, player-stat coverage, club coordinate coverage, source coverage, latest export date, validation status, and unresolved field categories.

Limitations are explicit in the UI and selectors: no values are fabricated or inferred from unavailable fields. The current app exports include xG but not xGA; player starts are not exported, so the impact view uses a transparent meaningful-minutes threshold instead. Missing values are excluded from metric-specific denominators rather than imputed.

## Repository Layout

```text
.
|-- data/
|   |-- raw/                               # Original roster scrape outputs and source HTML
|   |-- master/                            # THE canonical master workbook (version-controlled)
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
|-- site/                                  # The site: React + TypeScript + React Router + Vite
|-- docs/                                  # Status docs, handoff, and current-work checklist
`-- archive/local_artifacts/               # Local temp/cache artifacts, not pipeline inputs
```

## Data Model

The master workbook is treated like a small relational database:

- `players`: one row per player, keyed by `player_id`
- `squad_entries`: one row per player’s 2026 World Cup squad inclusion
- `clubs`: one row per canonical club
- `player_club_at_callup`: join table connecting players to clubs
- `coaches` and `referees`: one row per head coach and per match official
- `match_history`: one row per match, with scores and venues
- `player_stats` and `team_stats`: FIFA's tournament statistics
- `sources`: source registry
- `change_log`: the main corrections and updates
- `data_dictionary`: field notes for some of the sheets
- `raw_roster_import`: the original ESPN squad lists, kept for provenance

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

## Current Status

1. Data collection and cleanup phases (roster ingestion, stable IDs, Wikidata matching, club normalization, city geolocation) are complete.
2. The dataset is final-roster verified (2026-07-12/13):
   - all 48 squads cross-checked against FIFA's final lists — 1,221 confirmed, 27 cut (`squad_status=removed`), 27 late replacements ingested with generated IDs and Wikidata-enriched birthplaces;
   - `clubs` holds `461` canonical clubs collapsing to `397` geocoded city rows;
   - official FIFA stats (goals/assists/minutes/cards/goalkeeping) for all 1,231 registered players, team stats with computed W/D/L and stage reached, and all 104 matches;
   - coaches (48) and match officials (167) collected with sources registered.
3. The export pipeline (`refresh_all_exports.py`) regenerates everything from the workbook in one command with a strict integrity audit.
4. The site (`site/`, React + TypeScript + Vite) has seven pages. The navigation labels differ from the addresses, which are kept so old links work:
   - `Home` (`/`): what the dataset is, how it was built, and counts computed from the data;
   - `Club Map` (`/players-clubs`): a country-bubble world map that reveals club cities on zoom or selection, with cascading filters, club and player search, and auto-zoom to the filtered region;
   - `Squads` (`/national-teams`): sortable rosters with coach, captain, caps, and stage reached;
   - `Matches` (`/matches`): an interactive knockout bracket (click a team to trace its path) and every result grouped by stage, and by group within the group stage;
   - `Leaders` (`/stats`): leaderboards for goals, assists, goals plus assists, discipline, minutes, and goalkeeper saves, in totals or per 90, and a sortable team table;
   - `Analysis` (`/insights`): the squad composition scorecard, club and league impact, squad concentration, a two-team comparison, player efficiency, match and venue analysis, and a data-quality dashboard;
   - `Methodology` (`/sources`, under More): source attributions, how the dataset is built and checked, coverage counts, and the change log;
   - clicking any player name opens a detail panel with their photo and its attribution, bio, club, pre-tournament caps and goals, and tournament statistics.
5. The site is live on Netlify (https://worldcupplayertracker.netlify.app/). The post-final refresh ran on 2026-08-19, so the dataset covers the whole tournament.

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

## Tests And CI

Export-invariant tests live in `tests/` (pytest): unique IDs, cross-table referential integrity, the 48×26 active-roster shape, and `meta.json` counts matching every file. Run them with:

```bash
.venv/bin/pip install -r requirements-dev.txt   # once (adds pytest)
.venv/bin/python -m pytest
```

`.github/workflows/ci.yml` runs on every push to `main` and on pull requests: a **data** job (`pytest` + the strict export audit) and a **site** job (`pnpm typecheck` + `pnpm build`). The build step also guards the deploy — a missing imported `@data/*.json` fails CI rather than silently breaking the Netlify build.

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
- `scripts/data_pipeline/apply_post_import_fixes.py` and `scripts/data_pipeline/enrich_new_players_from_wikidata.py`: post-import corrections and Wikidata birthplace enrichment, applied to the canonical xlsx with timestamped backups
- `scripts/geolocation/build_city_country_lookup_from_clubs.py`: deduplicates club cities
- `scripts/geolocation/build_city_geocoding_workfile.py`: builds the city-level geocoding workfile
- `scripts/geolocation/apply_city_geocoding_results.py`: reapplies reviewed city geocoding decisions

## Next Step

The site is launched as a free static website on Netlify, as `docs/launch_guide.md`
describes, and the dataset is final. Follow-up work is listed in
`docs/deferred_dataset_and_prototype_todo.md`.
