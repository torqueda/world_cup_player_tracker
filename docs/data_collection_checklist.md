# Data Collection Checklist

This checklist now tracks the remaining data-side work that still matters before and during the first dashboard prototype.

## Current Data Status

- [x] Bootstrap roster data from the ESPN source article.
- [x] Correct malformed roster rows and obvious duplicates in the raw import.
- [x] Generate stable internal IDs for players, clubs, squad entries, and player-club links.
- [x] Match players to Wikidata and manually review difficult identity cases.
- [x] Pull reusable Wikimedia Commons image metadata where available.
- [x] Run read-only player identity validation against Wikidata facts.
- [x] Normalize clubs into the canonical club set.
- [x] Build the club geolocation baseline and propagate city geodata into the master workbook.
- [x] Verify the current workbook `clubs` and `player_club_at_callup` sheets align on club IDs.
- [x] Regenerate current app-ready JSON exports.
- [ ] Decide whether to normalize the two remaining player birthplace naming candidates.
- [ ] Decide whether to import historical manual-review provenance into the workbook.

## Current Workbook Readiness

- [x] `players` has `1,248` rows and unique `player_id` values.
- [x] `clubs` has `456` current canonical rows.
- [x] `player_club_at_callup` has `1,248` rows and no missing current `club_id` joins.
- [x] `clubs` matches `clubs_geocoded_corrected.csv` on canonical club text fields.
- [x] `clubs` contains `city_lat`, `city_lon`, `city_source_url`, `city_geo_source`, `city_match_confidence`, `city_key`, and `city_review_notes`.
- [x] `change_log` is populated and now exports to app-ready JSON.
- [ ] `manual_review_queue` is still intentionally empty in the workbook.
- [ ] `world_cup_history` remains a later expansion unless needed for the first prototype.

## Current Export Layer

- [x] Current workbook-backed CSV snapshots exist in `data/processed/master_exports/`.
- [x] Current audit outputs exist in `data/processed/master_exports/master_workbook_alignment_summary.json`.
- [x] Current birthplace review candidates exist in `data/processed/master_exports/player_birthplace_city_candidate_review.csv`.
- [x] Current frontend JSON exports exist in `data/processed/app_exports/`.
- [ ] Add additional export files later if the app needs derived summaries not yet materialized.

## Remaining Data Cleanups Worth Considering

- [ ] Decide whether `New York City` should stay as-is or be normalized to `New York` in `players`.
- [ ] Decide whether `Tashkent Region` should stay as-is or be normalized to `Tashkent` in `players`.
- [ ] Decide whether to carry historical player review queues into the master workbook for provenance.
- [ ] Decide whether to add birthplace geocoding later for a player-origin map.
- [ ] Decide whether to add coach and referee tables before or after the first prototype.
- [ ] Decide whether to add public-facing field documentation for image/source attribution before deployment.

## Prototype Readiness

- [x] The project is clear to begin frontend scaffolding against `data/processed/app_exports/`.
- [x] The current safest build strategy is a local-first browser app using React + TypeScript + Vite.
- [x] Scaffold the app shell.
- [x] Build the first data-backed route. Done: `Players & Clubs` (`site/src/routes/players-clubs-route.tsx`).
- [x] Add map rendering and filtering. Done: Leaflet map with team/league/country filters and search.
- [x] Add team and analytics views. Done: `National Teams` and `Insights` routes.
- [x] Decide on deployment only after the prototype proves the data model and interaction design. Decided 2026-07-13: free static website (Netlify/Cloudflare Pages), no downloadable app — see `docs/launch_guide.md`.
