# Current Work: Dashboard Prototype Checklist

This is the current operational checklist for moving from the workbook-backed dataset into the first real dashboard prototype.

- [x] Freeze the current workbook-backed dataset as the prototype baseline.
Outcome: `data/master/world_cup_2026_player_map_master.xlsx` is the working source of truth for the prototype phase.
Sets up: every downstream export and app join can reference one current authoritative dataset.

- [x] Export current workbook-backed CSV snapshots to `data/processed/master_exports/`.
Outcome: there are current CSV counterparts for `players`, `clubs`, `squad_entries`, `player_club_at_callup`, `sources`, and `change_log`.
Sets up: file-based scripts and manual checks can work from current data without reaching back into historical step folders.

- [x] Audit current club IDs and club text alignment.
Outcome: the current workbook is confirmed to have `456` clubs, `1,248` player-club rows, no missing current `club_id` joins, and no canonical-field drift from `clubs_geocoded_corrected.csv`.
Sets up: the frontend can join players to clubs without club-ID ambiguity.

- [x] Separate possible player birthplace naming follow-ups into a review file.
Outcome: any possible cross-sheet city-name cleanup is isolated to `data/processed/master_exports/player_birthplace_city_candidate_review.csv` instead of being auto-applied blindly.
Sets up: we can prototype now, while keeping the remaining naming decisions visible and easy to revisit later.

- [x] Regenerate `data/processed/app_exports/` from the current workbook.
Outcome: `clubs.json`, `cities.json`, `players.json`, `teams.json`, joins, sources, and `change_log.json` are up to date and app-ready.
Sets up: the React app can start from stable JSON inputs instead of reading Excel directly.

- [x] Scaffold a React + TypeScript + React Router + Vite app in the repo.
Outcome: the project gets a fast local development shell with typed components, routing, and a clear place for UI work.
Sets up: we can add one route at a time without mixing app scaffolding concerns with data-cleanup concerns.

- [x] Add a typed data-access layer that loads the JSON exports.
Outcome: `site/src/lib/data/types.ts` defines `Club`, `City`, `Player`, `Team`, `SquadEntry`, and `PlayerClubAtCallup`; `site/src/lib/data/index.ts` imports the six matching JSON files through the existing `@data` alias, casts them to those types (so a refreshed dataset with the same shape drops in without app changes), and exposes lookup/join helpers (`getClubById`, `getPlayerById`, `getTeamForPlayer`, `getClubForPlayer`, `getPlayersForClub`, `getSquadForTeam`, `getPlayerRoster`). The `Players & Clubs` route now renders live loaded counts and a real player→club→team join table, proving the layer end to end. `pnpm typecheck` and `pnpm build` both pass.
Sets up: route components can focus on presentation and filtering instead of raw parsing and data-shape cleanup.

- [x] Build the shared app shell and top-level navigation.
Outcome: `site/src/routes/root-layout.tsx` provides the shared header, status indicator, and `NavLink`-based tab navigation for `Overview`, `Players & Clubs`, `National Teams`, and `Insights`, with `<Outlet />` rendering each route's content underneath. Verified in-browser at mobile, tablet, and desktop widths, with correct active-tab highlighting on every route. Fixed a real CSS specificity bug where hovering the current tab visually reverted it to the inactive style (`.nav-link:hover` was outranking `.nav-link-active`); added `.nav-link-active:hover` in `site/src/styles.css` so the active tab stays highlighted under the cursor. Also replaced the stale scaffold-time status pill copy ("Scaffold phase complete once dependencies install") with copy reflecting the current phase now that the data layer is wired in. `pnpm typecheck` and `pnpm build` both pass.
Sets up: each screen can be built independently while still feeling like one coherent application.

- [x] Build the `Players & Clubs` screen first.
Outcome: chose Leaflet + `react-leaflet` as the mapping library (small, no API key, free OpenStreetMap tiles — see `site/src/components/players-clubs-map.tsx`). The route (`site/src/routes/players-clubs-route.tsx`) renders one marker per city from `cities.json`, sized by `club_count`; clicking a marker shows that city's clubs and their World Cup 2026 players via the data-access layer's `getClubsForCity`/`getPlayersForClub`/`getTeamForPlayer`. Filters for national team, league, club country, and a club/player text search narrow which markers show without resetting the map's pan/zoom; a new `getTeamsForClub` helper backs the team filter directly off `player_club_at_callup`. Verified end to end in-browser: filtering, marker selection, clearing filters, and mobile/desktop layout all work with no console errors. Two real bugs were found and fixed during verification: (1) `scrollWheelZoom` was scroll-jacking the page — a user scrolling past the map would accidentally zoom it instead — fixed by disabling it and relying on the zoom buttons/double-click; (2) the search box only matched `display_name`, so accented names like "Mbappé" didn't match a plain-ASCII search like "Mbappe" — fixed by also matching `name_ascii`/`club_name_ascii`. `pnpm typecheck` and `pnpm build` both pass.
Sets up: the route exercises the most important joins first and proves that the geolocation/export layer is working end to end.

- [x] Build the `National Teams` screen second.
Outcome: `site/src/routes/national-teams-route.tsx` adds a searchable list of all 48 squads (defaults to the first team so the screen never opens blank) next to a squad detail panel: live squad-size/clubs-represented/club-countries/replacements stats plus a full roster table (player, position, shirt number, club, league, country) sorted goalkeeper → defender → midfielder → forward, then by name. A new `getSquadRosterForTeam` helper in `site/src/lib/data/index.ts` joins `squad_entries` → `players` → `player_club_at_callup` → `clubs` for this, mirroring the existing `getPlayerRoster` pattern. Verified end to end in-browser across several teams (Algeria, Brazil, Netherlands) and at mobile/desktop widths, with no console errors and no horizontal overflow.
Sets up: the app structure expands from club geography into roster-centric exploration without changing the core data model.

- [x] Build the `Insights` screen third.
Outcome: `site/src/routes/insights-route.tsx` covers two angles from the existing dataset (no match-stat data needed, since `player_stats.json`/`team_stats.json` are still empty per `meta.json`):
  - **Country of birth**: a full sortable bar chart of all 66 birth countries; stat tiles for the most-represented country (France, 100), birth countries represented, and most-represented birth city; a chip list of the 16 countries tied for least-represented (1 player each); a "city spotlight" listing all 23 players born in Panama City; and two ranked lists (with ties included past the nominal top-5 cutoff) for teams with the most players born in the country they represent (8-way tie at 26/26) and the most born outside it (Curaçao leads at 25/26).
  - **Club at call-up**: a full bar chart of all 456 clubs by summoned players, plus a top-5 highlight (Manchester City F.C. leads with 19).
  - **Team explorer** (combines the requested "roster by birth country" and "roster by club" asks into one sticky sidebar panel): a searchable team picker, the selected team's full roster (player, birth country, club), and an emphasis chart of which countries that squad's clubs are based in, with the team's own country highlighted (e.g. Argentina: 2 of 26 play for Argentina-based clubs).
  - A small alias map (`TEAM_COUNTRY_ALIASES`) corrects 5 teams whose name doesn't literally match their birth_country/club-country spelling (e.g. `Czechia` team vs. `Czech Republic` birth country) so the "born in own country" comparisons are accurate.
  - New reusable `site/src/components/bar-list.tsx` (uniform and emphasis bar-chart modes) built per the `dataviz` skill (single-hue magnitude bars, emphasis form for the highlighted-country breakdown, direct value labels, no color-by-value on nominal categories).
  - Found and fixed a real CSS grid bug during mobile verification: nested `display:grid` containers without an explicit `minmax(0, 1fr)` track were sizing to their content's max-content width instead of the viewport, causing the stat-tile grid to overflow at mobile widths. Fixed in `site/src/styles.css` (`.insights-grid`, `.insights-main`).
  - Three additional insights were proposed and approved by the user, then added: **player diaspora** (17 non-competing countries still produced a World Cup 2026 player, e.g. Italy (3), Denmark (3)); **average squad age** (measured as of the 2026-06-11 kickoff — Ivory Coast youngest at 25.7, Panama oldest at 30.4, 27.9 average across all squads — plus a per-team average shown in the team explorer); and **top leagues sending players** (Premier League leads with 158, across 102 distinct leagues), mirroring the club chart's top-5-plus-full-list treatment.
  - Verified end to end in-browser (bar charts, tie handling, team switching, mobile/desktop layout, no console errors); confirmed no regressions on Overview/Players & Clubs/National Teams at mobile width. `pnpm typecheck` and `pnpm build` both pass.
Sets up: future player-stat and team-stat datasets can plug into an already-existing analysis surface.

- [x] Harden the export pipeline and repo hygiene before the QA phase (2026-07-12).
Outcome: `scripts/export/refresh_all_exports.py` now runs the full CSV → audit → JSON refresh in one command, with the audit in a new `--strict` mode that exits non-zero (and stops the pipeline) if any integrity check fails; all three export scripts resolve their default paths relative to the repo root so they work from any working directory; `meta.json`/audit-summary paths stay repo-relative; `cities.json` gained the `city_ascii` field the deferred-todo doc identified (typed in `site/src/lib/data/types.ts`). The repo is now a git repository (`main` branch, root `.gitignore`) and `requirements.txt` pins the Python pipeline dependencies. Verified: two consecutive pipeline runs produce byte-identical outputs, all integrity checks pass, `pnpm build` passes, and the running app shows correct counts with no console errors.
Sets up: dataset refreshes are one command, integrity regressions fail loudly instead of silently reaching the app, and the project history is version-controlled from the QA phase onward.

- [x] Add QA, provenance, and deployment decisions after the first working prototype exists (satisfied 2026-07-13).
Outcome: the `Data & Sources` page carries statement-style attributions with links, the change log, method notes, a "data last regenerated on …" freshness stamp (driven by a new `exported_at` field in `meta.json`, which also powers the header pill), and a link to the public GitHub repo; the hosting decision is made and documented in `docs/launch_guide.md`. Of the queued QA data findings, `Gaziantep F.K.`'s stray `league="dissolution"` was corrected to Süper Lig in the canonical workbook (change-logged; the dissolution note belonged to Mazatlán F.C.); the league-name duplicate reconciliations are judgment calls and moved to the deferred to-do.
Sets up: provenance is a user-visible feature, not a spreadsheet artifact.
Original QA findings queue (kept for history):
  - `Gaziantep F.K.` has `league = "dissolution"` in the `clubs` sheet — not a league name; needs a manual fix in the workbook (and check whether the dissolution note belongs on Mazatlán F.C. per `club_triage_manual_checks.md`).
  - Likely duplicate league spellings to reconcile (or confirm as genuinely distinct): `Jordan Premier League` (1 club) vs `Jordanian Pro League` (2); `South African Premier Division` (2) vs `South African Premiership` (1) vs `Premier Soccer League` (1); `Liga Portugal` (5) vs `Primeira Liga` (3); `Iraq Stars League` (3) vs `Iraqi First Division League` (1 — may be a real second tier).
  - The two birthplace naming candidates in `player_birthplace_city_candidate_review.csv` are still undecided (New York City / Tashkent Region).
  - `club_triage_manual_checks.md` has a truncated line ("All league values of Uruguayan Segunda División changed to ") — record what it was actually changed to.

- [x] Collect the final dataset: rosters cross-checked, replacements identified, coaches, referees, player/team stats, and all match results through the quarterfinals (2026-07-12).
Outcome: hybrid collection (Wikipedia scrapers + browser reading of fifa.com rendered pages) produced import-ready workbook sheets in `data/processed/workbook_import/` — 1,221 players confirmed on final squads, 27 marked removed, 27 late replacements with generated IDs, 17 new clubs flagged for review, 1,210 player-stat rows, 48 team-stat rows with computed W/D/L and stage reached, 104 matches, 48 coaches, 167 officials, and new source-registry rows. Full detail and the import order: `docs/dataset_finalization_report_2026-07-12.md`. Note: per the 2026-07-12 decision, dataset finalization now comes BEFORE the QA/provenance item above, since QA needs the final data in hand.
Sets up: importing these sheets into the Google Sheets master, re-downloading the xlsx, and running `refresh_all_exports.py` makes the app stats-ready for the pre-semifinal deploy.

- [x] Import the workbook_import sheets into the master workbook and resolve the review files (2026-07-12/13).
Outcome: the workbook gained the final-roster updates, new players/clubs, stats (including goalkeeping), matches, coaches, referees, and source rows. The user resolved all 21 unmatched stat rows (including confirming FIFA's "Mohammad Abughoush" = Mohammad Taha and Kim Tae-hyun = Kim Tae-hyeon), remapped 12 replacement clubs to existing canonical clubs, filled the 5 genuinely new clubs (league/country/city/coords), and corrected the Austrian Football Bundesliga naming plus Grazer AK's city/stadium. The 27 replacements were then Wikidata-enriched (DOB-confirmed matches; only Mohammad Taha and Cho Wi-je still lack a birthplace, as Wikidata has none). `refresh_all_exports.py` passes the strict audit; clubs pending geocoding count is zero.
Sets up: the dataset is final for the v1 deploy; only the semifinal/final stats refresh remains optional.

- [x] Manually cross-check the final roster against FIFA's official tournament pages before the dataset is called final.
Outcome: done as part of the final-dataset collection — FIFA's own registered-player list (1,231 stat rows) reconciled 1:1 against the imported final squads, closing the loop the original checklist item asked for.
Sets up: the definitive dataset is locked.

- [ ] LAUNCH BLOCKERS (revised 2026-07-13) — what still stands between this project and a public, "complete" v1, excluding style/content polish.
  Resolved since the first version of this list: ~~Google Sheets sync~~ (obsolete — **the local `data/master/world_cup_2026_player_map_master.xlsx` is now the canonical Master List**, the Sheets copy is retired, and the user corrected the remaining items directly, including the last two missing birthplaces); ~~first git commit + push~~ (done — https://github.com/torqueda/world_cup_player_tracker); ~~QA/provenance item~~ (Data & Sources page, above).
  1. **Connect the host and smoke-test the live URL** (~15 min). Netlify or Cloudflare Pages with base `site`, build `pnpm build`, publish `site/dist`; then click through all seven routes on the live URL (deep links like `/stats` exercise the already-in-place `_redirects` SPA fallback). Exact steps: `docs/launch_guide.md`.
  2. **Post-tournament data refresh** (time-bound, ~1–2 h after the July 19 final). Re-run the two Wikipedia scrapers and the three FIFA captures, rebuild import sheets, update the workbook, refresh exports, commit + push (auto-deploys). Launching before the semis with "through quarterfinals" data is fine; the dataset is only *complete* once the final's results are in.
Outcome: a public URL non-technical people can open, backed by the version-controlled canonical workbook, with the full tournament recorded.
Sets up: v1.0 — after this, everything else (images, fuzzy search, code-splitting, new insights, the league-name reconciliations) is enhancement, not completion.

Final outcome:
A browser-based prototype running locally from React + TypeScript + Vite, backed by `data/processed/app_exports/`, with a real map-backed `Players & Clubs` view, a connected `National Teams` view, and an expandable `Insights` surface for future stats.
