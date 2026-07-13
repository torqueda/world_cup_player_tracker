# Deferred Dataset And Prototype TODO

These items are intentionally deferred so they can be handled when the timing is more efficient, instead of blocking the first dashboard prototype.

## Dataset follow-ups

- [x] *(Collection done 2026-07-12)* Refresh the player roster after final injury replacements and other late squad changes are settled. Final squads scraped and reconciled; import sheets in `data/processed/workbook_import/` await the Google Sheets import. See `docs/dataset_finalization_report_2026-07-12.md`.
- [x] Update Avazbek Ulmasaliev's `place_of_birth` from `Tashkent Region` to `Fergana` when the roster update pass happens. *(Done — verified `Fergana` in the current workbook, 2026-07-13.)*
- [x] *(Done 2026-07-13)* Collect team→confederation data (AFC/CAF/CONCACAF/CONMEBOL/OFC/UEFA). The user added full member lists to `data/raw/confederations.md`; the export pipeline now parses it into `confederations.json`, all 48 teams resolve, and the site uses it for the Insights confederation section (progression funnel, cross-confederation win matrix, per-confederation explorer), the donut "sort by confederation" option, and a National Teams confederation filter.
- [ ] Optional post-semifinal stats refresh before the final: re-run the two Wikipedia scrapers, re-capture the three FIFA surfaces, re-run `build_workbook_import_sheets.py`, update the workbook, and refresh exports.
- [ ] Keep `New York City` as the preferred wording instead of normalizing it down to `New York`.
- [ ] Re-run any downstream exports that depend on player birthplace text after the roster refresh.

## Provenance and review-history follow-ups

- [ ] Decide whether `manual_review_queue` should remain in the workbook at all.
- [ ] If `manual_review_queue` is removed, decide whether any manual-review provenance still needs to be preserved elsewhere.
- [ ] If provenance is still useful, decide whether to consolidate it from files such as `manual_review_queue_step3.csv`, geolocation review notes, and other project-side manual decision logs.

## Prototype architecture follow-ups

- [ ] Keep the prototype wired to generated exports so a final definitive dataset can replace the current baseline without redesigning the frontend.
- [x] Add the typed data-access layer that reads from `data/processed/app_exports/`. Done via `site/src/lib/data/`.
- [ ] Decide whether the app should keep direct `@data` imports, move to a runtime fetch model from copied files in `public/`, or use route-level dynamic `import()` code-splitting. Deliberately staying with direct `@data` imports for the initial prototype; revisit after the prototype is complete, pending mentor guidance. Three options on the table:
  1. **Current: direct `@data` imports.** Simplest code (no loading states, fully typed at compile time), but every route pays for all six datasets in one bundle. As of the `Players & Clubs` map shipping (Leaflet added), the production JS is a single ~3.35 MB (501 KB gzip) chunk.
  2. **Runtime fetch from a `public/`-copied dataset.** Shrinks the JS bundle and lets routes fetch only what they need, at the cost of loading states, fetch error handling, a small build step to copy `data/processed/app_exports/*.json` into `site/public/`, and slightly weaker out-of-the-box type safety.
  3. **Route-level dynamic `import()` (proposed alternative).** Keeps the simplicity and type safety of direct imports, but defers each dataset's `import()` to the route that needs it, so Vite/Rollup code-splits it into its own chunk automatically — no fetch/loading-state code and no `public/` copy step required. Likely the best effort-to-benefit tradeoff if bundle size turns out to matter, but not yet decided.
- [ ] Decide later whether player birthplace geocoding should become a separate map surface.
- [ ] Decide later whether coach and referee data should be added before or after the first working prototype.

## Stats, roster, and referee sourcing follow-ups

- [ ] Evaluate FIFA's official tournament pages as the eventual ground-truth source for final player/team stats, roster finality, and referees (if referee data is ever added):
  - https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/player-statistics
  - https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/team-statistics
  - https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/standings
  - https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/teams
- [x] *(Superseded 2026-07-12)* Before any automated collection from fifa.com: reach out to FIFA directly, describe the project (a non-commercial World Cup player/club tracker), and ask for explicit permission to use/collect their statistics and roster data. Do not build a scraper against fifa.com before this is resolved. **Decision: proceeded without prior outreach** — non-commercial factual-data use, robots.txt permits the pages, and collection was human-paced browser reading of rendered pages (no bot-protection circumvention). Recorded in `docs/dataset_finalization_report_2026-07-12.md`.
- [x] *(Resolved by the 2026-07-12 collection run — rendered-page browser reading worked; kept for history.)* Initial technical due-diligence (2026-07-09): `fifa.com/robots.txt` only disallows one narrow pattern (`/*?archive?filters=`) — nothing blocks the tournament/stats/teams pages above. However, fetching those pages' raw HTML returns an empty shell; they are JavaScript-rendered single-page apps, so a plain HTTP scrape gets nothing. Getting real data would need either a headless browser (e.g. Playwright) driving the rendered page, or reverse-engineering the JSON API the page calls internally (not yet identified — requires inspecting Network/XHR requests in a real browser, which wasn't available this session). Attempts to locate FIFA's actual Terms of Use text hit redirects and a 404 and were not confirmed — this is a separate, unresolved question from the permission ask above and matters regardless of technical feasibility.

## Search and text-matching follow-ups (revisit after beta-testing)

- [x] *(Export side done 2026-07-12)* City names have no ASCII counterpart in the export (`cities.json`/the `City` type only has `city`, unlike `clubs`/`players`, which both carry a `_ascii` field). `cities.json` now carries `city_ascii` (added in `scripts/export/export_master_workbook_to_json.py`, typed in `site/src/lib/data/types.ts`); wiring it into the search UI remains deferred with the rest of this section. (Background: club-name searches were already accent-insensitive via `club_name_ascii` — e.g. `Widzew Lodz` matched `Widzew Łódź` — but a search landing on a city by its own name had no ASCII fallback until now.)
- [ ] Plain substring search already handles simple contained-name cases — confirmed `Al-Najma` matches `Al-Najma SC (Saudi Arabia)` today, since the shorter query is literally contained in the canonical name. It does **not** handle: typos, abbreviations that aren't substrings (e.g. "Man United" vs. "Manchester United"), or alternate/historical names that differ from the canonical name entirely. Fix ideas to evaluate later: a small fuzzy-matching library (e.g. Fuse.js) for typo tolerance, and/or surfacing known aliases from `data/processed/club_normalization_working/club_alias_map.csv` (`raw_club_name` → `canonical_club_name`, 512 rows already collected during club normalization) as an additional searchable alias list instead of matching the canonical name only.
- [ ] Explicitly deferred until after the dashboard has been beta-tested with real users, so real search misses (not hypothetical ones) drive which of the above is worth building first.
