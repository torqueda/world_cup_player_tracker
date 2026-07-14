# Dataset Finalization Report — 2026-07-12

Collection run for the final dataset, done two days before the semifinals (France–Spain July 14, England–Argentina July 15). All tournament data is current **through the quarterfinals**, which is exactly the "deploy right before the semifinals" target state.

## What was collected and from where

| Data | Source | Where it landed |
|---|---|---|
| Final 26-man squads (all 48 teams), shirt numbers, captains, DOB, caps/goals pre-tournament, clubs | Wikipedia squads page (scripted; HTML snapshot archived) | `data/processed/final_roster_reconciliation/wikipedia_final_squads.csv` |
| Coaches (48) | same | `wikipedia_coaches.csv` |
| Per-team squad announcement/replacement prose | same | `wikipedia_squad_notes.csv` |
| Match officials: 51 referees, 88 assistants, 28 VARs, with match assignments | Wikipedia officials page (scripted; snapshot archived) | `wikipedia_match_officials.csv` |
| Player stats: goals, assists, minutes for all 1,231 registered players | fifa.com player-statistics (browser collection) | `data/raw/fifa_player_stats_golden_boot_tab.csv` |
| Player cards: 235 players with yellow/red/indirect-red | fifa.com Discipline tab | `data/raw/fifa_player_stats_discipline_tab.csv` |
| Team stats: goals, assists, xG, possession (48 teams) | fifa.com team-statistics | `data/raw/fifa_team_stats_attacking_tab.csv` |
| All 104 matches: 100 results (with penalty shootouts) + 4 remaining fixtures, stages, stadiums, dates | fifa.com scores-fixtures | `data/raw/fifa_scores_fixtures_snapshot.txt` |

## Roster reconciliation result

- **1,221 of our 1,248 players confirmed** on final FIFA squads (with shirt number, captain flag, caps/goals attached).
- **27 players did not make the final squads** → marked `squad_status=removed` in the import sheet. Notably this resolves the old count anomalies: Portugal trimmed 27→26 (Ricardo Velho out), Germany filled its open 26th spot.
- **27 new players** (late replacements) → full new-row import sheets generated with stable IDs following the existing scheme, flagged `manual_review_flag=TRUE` for later Wikidata/birthplace enrichment.
- **17 of the new players' clubs are not in our 456 canonical clubs** → new club rows generated, flagged for league/country/city/geocoding review.

## Import-ready sheets (`data/processed/workbook_import/`)

Import into the Google Sheets master in this order, then re-download the xlsx and run `scripts/export/refresh_all_exports.py`:

1. `clubs_new_rows_for_review.csv` → append to `clubs` (fill league/country/city first, or import flagged and fix after; city/geodata needed before they appear on the map).
2. `players_new_rows.csv` → append to `players`.
3. `squad_entries_new_rows.csv` → append to `squad_entries`.
4. `player_club_at_callup_new_rows.csv` → append to `player_club_at_callup`.
5. `squad_entries_updates.csv` → update existing rows by `squad_entry_id` (shirt_number, squad_status, verified_at; caps/captain columns are new — add them or skip). 27 rows have `squad_status=removed`.
6. `player_stats.csv` (1,210 rows) → new `player_stats` sheet.
7. `team_stats.csv` (48 rows, incl. computed W/D/L/GF/GA and stage reached) → new `team_stats` sheet.
8. `world_cup_history_matches.csv` (104 rows) → `world_cup_history` sheet.
9. `coaches.csv` (48) and `referees.csv` (167) → new sheets (the export pipeline already picks both up).
10. `sources_new_rows.csv` → append to `sources`.
11. Log the import in `change_log`.

The export pipeline (`refresh_all_exports.py`) already emits `player_stats.json`, `team_stats.json`, `world_cup_history.json`, `coaches.json`, `referees.json` the moment these sheets exist.

## Manual review queue (before calling the dataset final)

- `workbook_import/player_stats_unmatched_for_review.csv` — 21 FIFA stat rows that need hand-linking to a `player_id` (nicknames/aliases: Trezeguet, Gatito Fernández, Ederson (Brazil GK), Pico Lopes, Diney Borges, Giovanni/Gio Reyna, Alex/Alejandro Zendejas, Maxi/Maximiliano Araújo, etc.).
- `final_roster_reconciliation/roster_match_report.csv` — 32 rows with `dob_check=MISMATCH`. Several look like **wrong-person Wikidata matches in our data** (Mexico's Jorge Sánchez 1993 vs 1997, Scotland's Liam Kelly and Ross Stewart — duplicate-name players). Treat manual verification notes as higher authority per project rules, but these specific ones deserve a recheck.
- The `South Korea: Kim Tae-hyun ↔ Kim Tae-hyeon` fuzzy match (DOB mismatch) may be two different players — verify.
- 27 `is_replacement=TRUE` rows have blank `replaced_player_id`; `wikipedia_squad_notes.csv` has the per-team announcement prose to link who replaced whom.
- Avazbek Ulmasaliev `place_of_birth` fix (`Tashkent Region` → `Fergana`) — do it during this import pass (deferred-todo item).
- New players lack Wikidata IDs, birthplaces, and images: run `scripts/data_pipeline/match_players_to_wikidata.py` against the 27 new rows (or hand-fill; it's only 27).

## Still missing after this run (known, accepted)

- **Semifinal/final results and updated stats** — re-run before/at deploy if you want to include SF results: re-run the two Wikipedia scrapers (they refetch live), recapture the three FIFA surfaces (the browser steps are documented by the raw snapshot formats), then `build_workbook_import_sheets.py` regenerates everything.
- **Matches-played per player** — FIFA's stats tabs don't expose appearances directly; minutes>0 is a proxy. Could be derived later from per-match lineups if wanted.
- **Goalkeeping stats (saves, clean sheets)** — available on FIFA's Goalkeeping tab, not collected in this pass; same collection recipe if wanted.
- **Player images** — per the 2026-07-12 decision, Commons images are dropped; license-free per-country images to be sourced manually later.
- **Birthplace geocoding, coach/referee Wikidata enrichment** — post-deploy features.

## Decision record

Scraping approach approved 2026-07-12: hybrid (Python scrapers for Wikipedia's static pages; browser-pane collection from fifa.com's rendered pages, stopping rather than evading if blocked; sofifa skipped). This supersedes the earlier "ask FIFA before any automated collection" note in `docs/deferred_dataset_and_prototype_todo.md` — rationale: non-commercial factual-data use, robots.txt does not disallow these pages, and collection was human-paced from rendered pages only.

---

**Addendum 2026-07-13:** the local `data/master/world_cup_2026_player_map_master.xlsx` is now the **canonical Master List**; the Google Sheets copy is retired and the "replicate to Sheets" instructions above are obsolete (kept for history). The repo is public at https://github.com/torqueda/world_cup_player_tracker, so the workbook is version-controlled. All remaining review items from this report were resolved directly in the canonical workbook (birthplaces incl. Taha/Cho Wi-je, GK columns, club fills, Gaziantep league fix); confederations were added via `data/raw/confederations.md`.
