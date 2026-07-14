# Roadmap: From Working Prototype To Deployed v1

Created 2026-07-12. This is the framework for the remaining life of the project, picking up where `docs/current_work_dashboard_prototype_checklist.md` ends. Each phase lists its goal, the concrete tasks, and the scripts that carry it (existing or still to be written). Phases A–B can overlap; C depends on B for stats-backed features; D is last.

## Where we are

The prototype is real: four working routes, a typed data layer over `data/processed/app_exports/`, and a one-command refresh pipeline (`scripts/export/refresh_all_exports.py`) with a strict integrity audit. The repo is now under git. What's left is (A) QA and provenance polish, (B) locking the definitive dataset and adding stats, (C) the features that need that data, and (D) deployment.

**Reordered 2026-07-12: Phase B runs before Phase A** (dataset finalization first, then QA — QA needs the final data in hand). Phase B's collection is now DONE: see `docs/dataset_finalization_report_2026-07-12.md` for what was collected and the workbook import order. The FIFA permission-email step was superseded by the decision to collect from rendered pages directly. Commons player images are dropped in favor of manually sourced license-free per-country images (Phase C item 1 changes accordingly).

## Phase A — QA and provenance (current phase)

Goal: the data shown is trustworthy and traceable, with a working UI in hand.

1. Fix the queued league-field findings (see the QA item in the current checklist): `Gaziantep F.K.` league `dissolution`, and the duplicate league spellings (Jordan, South Africa, Portugal, Iraq). Edit in the master workbook, log in `change_log`, then re-run `refresh_all_exports.py`.
2. Decide the two birthplace naming candidates (`player_birthplace_city_candidate_review.csv`).
3. Surface provenance in the UI: a `Sources & Changes` route (or Overview section) rendering `sources.json` and `change_log.json`, plus a "last updated" stamp from `meta.json` (add an `exported_at` timestamp to `meta.json` — small export-script change).
4. Image/attribution readiness: before any public deployment, player images from Wikimedia Commons must show author + license + source link wherever an image is displayed. Add an attribution component when player photos ship (Phase C).
5. Repo hygiene: make the first git commit; delete the cleanup candidates listed at the bottom once confirmed.

Scripts: existing pipeline only, plus the small `exported_at` addition.

## Phase B — Lock the definitive dataset and gather stats

Goal: final rosters verified against FIFA's official pages, and `player_stats` / `team_stats` populated.

1. **Final roster cross-check (manual, already on the checklist).** Use FIFA's teams pages as ground truth for the 48 squads; record corrections in the workbook + `change_log`. No scraping needed for a manual check.
2. **FIFA permission decision.** The deferred-todo doc already documents the constraint: do not scrape fifa.com before FIFA answers the permission request. Send that email now — it's the longest-lead item in the project. Outcomes:
   - Permission granted → build a stats collector (headless browser or their internal JSON API) as `scripts/stats_ingestion/collect_fifa_stats.py`.
   - No/silence → fall back to manually keyed headline stats (48 team rows and a top-N player subset are very feasible by hand), or an openly licensed alternative source (e.g. Wikipedia match pages, with per-source citation rows in `sources`).
3. **Stats schema.** Add `player_stats` and `team_stats` sheets to the workbook (the export pipeline already looks for them and currently emits empty arrays, so the moment rows exist they flow to the app). Suggested minimal columns:
   - `player_stats`: `player_id`, `tournament`, `matches_played`, `minutes`, `goals`, `assists`, `yellow_cards`, `red_cards`, `source_id`, `verified_at`.
   - `team_stats`: `team_code`, `tournament`, `matches_played`, `wins`, `draws`, `losses`, `goals_for`, `goals_against`, `final_rank_or_stage`, `source_id`, `verified_at`.
   Keep `source_id` joining to the `sources` sheet so every stat is traceable.
4. **Roster-change snapshots (Step 7 from the original plan).** Write `scripts/data_pipeline/snapshot_and_diff.py`: dump current CSV snapshots to `data/snapshots/YYYY-MM-DD/`, diff against the previous snapshot, and emit proposed `change_log` rows instead of silently overwriting. This is what makes "recent changes" honest during the tournament.
5. Re-run `refresh_all_exports.py` after every workbook change; strict audit guards the joins.

## Phase C — Feature additions on the final data

Ordered by value-per-effort:

1. **Player detail cards**: click a player anywhere → card with photo (with Commons attribution), DOB/age, birthplace, position, club, squad number, source links. Uses only existing fields.
2. **Sources & change-log route** (from Phase A if not done yet).
3. **Stats views**: once `player_stats`/`team_stats` land, extend `Insights` (top scorers, team performance vs. squad-age/diaspora angles — the surface was explicitly built for this).
4. **Search upgrades** (deferred until beta feedback per the deferred-todo doc): wire `city_ascii` into the map search; then fuzzy matching (Fuse.js) and/or the 512-row `club_alias_map.csv` as searchable aliases.
5. **Birthplace map**: a second map surface for player origins; needs birthplace geocoding (`birth_lat`/`birth_lon` are in the schema but unpopulated) — reuse the city-geocoding workflow (GeoNames) that already worked for clubs.
6. **Bundle-size decision** (pre-deployment): the single ~3.4 MB JS chunk should be split. The deferred-todo doc's option 3 (route-level dynamic `import()`) is the recommended path — keeps type safety, no fetch layer, Vite code-splits automatically.

## Phase D — Deployment

Goal: a public URL with a repeatable update path.

**Update 2026-07-13:** the concrete how-to lives in `docs/launch_guide.md` — decision made
there: static website on Netlify/Cloudflare Pages (free), no downloadable app. This phase
is now **complete**: the repo is on GitHub, the site is live on Netlify at
https://verdant-cactus-1e0657.netlify.app (auto-deploy on push, `site/public/_redirects`
SPA fallback in place), and it has been smoke-tested and used by other testers. The only
remaining launch item is the post-final data refresh after the July 19 final.

1. **Hosting choice.** The app is a pure static site (no backend, data baked in at build time). Any of GitHub Pages / Netlify / Cloudflare Pages / Vercel works free-tier. Recommendation: **GitHub Pages via GitHub Actions**, since the repo is heading to GitHub anyway and the update story becomes "push → deploy".
2. **Deployment checklist:**
   - Push the repo to GitHub (first commit → remote).
   - Add a workflow: on push to `main`, `pnpm install && pnpm build` in `site/`, publish `site/dist/`.
   - Set Vite `base` if serving under a subpath (`/world_cup_player_tracker/` on project Pages).
   - Client-side routing fallback: use a hash router or the 404.html redirect trick on Pages (or `_redirects` on Netlify — this is the one reason to prefer Netlify/Cloudflare if we keep the browser-history router).
   - Verify Leaflet/OSM tile usage stays within the OSM tile-usage policy (fine at hobby scale; add proper attribution — already present).
   - Confirm image hotlinking policy: Commons allows hotlinking, but attribution UI (Phase A/C) must ship first.
3. **Update workflow during the tournament:** edit workbook → `refresh_all_exports.py` → review diff → commit → push → auto-deploy. The snapshot/diff script (Phase B.4) feeds `change_log`, and the site shows "last updated".
4. **Post-launch:** beta feedback drives the deferred search items; `world_cup_history` becomes the expansion surface after the tournament.

## Cleanup candidates (marked for deletion, not yet deleted)

Safe to delete — generated/system junk, all reproducible or worthless:

- All `.DS_Store` files (root, `scripts/`, `data/master/`, `data/processed/`, and the two inside geolocation folders) — now gitignored anyway.
- `docs/.Rhistory` (0 bytes; R was never part of the pipeline).
- `scripts/geolocation/__pycache__/`, `scripts/export/__pycache__/` — Python bytecode caches.
- `archive/local_artifacts/` (entire folder, and with it `archive/` itself): contains only copied `.DS_Store` files, stale `.pyc` caches, and an Excel lock file (`~$step5_final_import_ready.xlsx`). It self-describes as "not pipeline inputs" and none of it is provenance.
- `.pnpm-store/` at the repo root (8 KB stray store from a pnpm invocation; the real store is global).
- `site/dist/` — build output, regenerated by `pnpm build` (gitignored; delete or keep freely).

One-liner once approved:

```bash
find . -name .DS_Store -not -path "./site/node_modules/*" -delete && \
rm -rf archive .pnpm-store docs/.Rhistory scripts/geolocation/__pycache__ scripts/export/__pycache__
```

Workbook cleanup (manual, user-side — like the other direct workbook edits): the
`manual_review_queue` sheet in `data/master/world_cup_2026_player_map_master.xlsx` is
**marked for deletion** (2026-07-13). It is empty (0 rows), read by nothing in the app, and
was never the source of user-facing provenance (the `Data & Sources` page + public repo
cover that). The export pipeline already tolerates its absence, so deleting the sheet needs
no code change. See `docs/deferred_dataset_and_prototype_todo.md` → "Provenance and
review-history follow-ups".

Keep (provenance, per README policy): `data/processed/club_geolocation_outdated/`, `club_normalization_*`, `stable_ids_initial/`, the dated backup CSVs in `club_geolocation_baseline/`, `data/raw/`.

Relocate rather than delete: `club_triage_manual_checks.md` (root) → `docs/` — it is manual-decision provenance, and one of its lines is truncated (see the QA item in the current checklist).
