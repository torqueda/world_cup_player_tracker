Current status note:
Use `README.md`, `docs/handoff.md`, and `docs/current_work_dashboard_prototype_checklist.md` for the authoritative current state of the project. This file is best treated as historical running notes and background context.

We are building a 2026 FIFA World Cup player-club interactive map and dashboard.

The project’s ultimate goal is to create a public-facing, data-rich website, potentially self-hosted, where users can explore every 2026 World Cup player by club, national team, birthplace, player bio data, images, and analytical views. This is not intended to be a simple copy of an existing Google My Maps project. The target product should eventually be a proper web dashboard/site with map interactions, filters, player cards, club summaries, data-source transparency, and roster-update tracking.

The project has two major parts:

1. Assemble, normalize, validate, and maintain the player/club/source dataset.
2. Build the website/dashboard code that lets users access and explore the dataset.

The data model currently lives in a Google Sheets workbook with these sheets:

raw_roster_import
players
squad_entries
clubs
player_club_at_callup
world_cup_history
sources
change_log
manual_review_queue
data_dictionary

The important principle throughout is that the spreadsheet is structured like a relational database. Do not collapse everything into one giant denormalized sheet. Stable internal IDs are used for joins, and external IDs like Wikidata QIDs are stored separately.

Current schema purpose:

raw_roster_import:
Raw imported roster rows from the original source. Preserve source wording here.

players:
One row per actual player. Uses stable player_id as the internal primary key. Contains Wikidata ID, display name, DOB, birthplace, image metadata, source URLs, confidence flags, and notes.

squad_entries:
One row per player’s inclusion in the 2026 World Cup squad. Links to players via player_id.

clubs:
One row per unique club. This is not fully normalized yet and is the next major task.

player_club_at_callup:
Links each player to the club listed at call-up/source time. Uses player_id and club_id.

world_cup_history:
Currently empty or not yet built. Intended for previous World Cup participation data.

sources:
Source registry for roster, bio, image, club, and future update sources.

change_log:
Currently empty or minimal. Intended to track roster changes, corrections, replacements, manual overrides, and future update diffs.

manual_review_queue:
Contains review items produced by scripts or manual QA.

What has already been done:

STEP 1 — Bootstrap rosters from aggregator page

A scraper was written and modified to pull roster data from ESPN’s all-48-teams World Cup squad article into raw_roster_import.csv. The original import had parser issues caused by missing closing parentheses in the source text. These were manually corrected:

Türkiye:
Original malformed text merged Hakan Calhanoglou and Kaan Ayhan.
Corrected into:
Hakan Calhanoglou — Inter Milan
Kaan Ayhan — Galatasaray

United States:
Original malformed text merged Tyler Adams and Sebastian Berhalter.
Corrected into:
Tyler Adams — AFC Bournemouth
Sebastian Berhalter — Vancouver Whitecaps

There was also a duplicate Elias Saad row for Tunisia. That was removed.

Known roster-count exceptions:
Germany intentionally has 25 listed players because one spot was left open.
Portugal has 27 listed players because ESPN listed a fourth goalkeeper.
Tunisia originally looked like 27, but after removing the duplicate Elias Saad row, it resolved to 26.

After corrections, the data had:
players: 1,248
squad_entries: 1,248
player_club_at_callup: 1,248
clubs: 511

STEP 2 — Generate stable IDs

A script named generate_stable_ids.py was produced and run. It generated CSVs for:

players.csv
squad_entries.csv
clubs.csv
player_club_at_callup.csv
sources.csv
manual_review_queue.csv
world_cup_history.csv
change_log.csv

Important ID design decision:
Use internal permanent IDs as primary keys. Do not use Wikidata IDs as player_id. Wikidata IDs are external identifiers stored in wikidata_id.

Examples:
player_id = p_usa_tyler_adams_a1b2c3d4
club_id = c_afc_bournemouth_8e7f6a5b
squad_entry_id = se_wc2026_usa_<hash>
player_club_callup_id = pc_wc2026_<hash>

Do not change player_id during later enrichment. All joins depend on it.

STEP 3 — Match players to Wikidata

A script named match_players_to_wikidata.py was produced and run. It searched Wikidata, scored candidates, and populated Wikidata-related fields for high-confidence matches. It produced:

players_wikidata_enriched.csv
wikidata_candidate_matches.csv
manual_review_queue_step3.csv
wikidata_match_summary.csv

Initial Step 3 results:
1,152 auto-matched players
96 players needed manual identity review

A later audit found 6 likely wrong auto-matches caused by same-name historical players. These were manually reviewed/fixed:

Roberto Fernández
Víctor Muñoz
Joao Paulo
Nuno Mendes
Éderson
Vitinha

The 96 manual-review players were then manually checked. The user manually edited the relevant fields, including:
wikidata_id
display_name
name_ascii
date_of_birth
place_of_birth
birth_country
bio_source_url
manual_review_flag
notes

The notes column should indicate manual QID matching / manual verification where applicable.

Important rule:
players_wikidata_enriched.csv already contains all 1,248 players. Manual-review players should not be appended. They are existing rows that need to be updated in place.

STEP 4 — Pull image metadata from Wikimedia Commons

A script named populate_commons_image_metadata.py was produced and run against the then-current players file. It used each player’s Wikidata QID to fetch Wikidata P18 images and then pulled Commons image metadata through the Commons MediaWiki API.

It produced:

players_image_metadata_enriched.csv
image_metadata_matches.csv
image_metadata_review_queue.csv
image_metadata_summary.csv

Reported output:
total_players: 1,248
players_with_wikidata_id: 1,248
players_with_image_commons_title: 966
players_with_image_url: 966
players_with_image_author: 966
players_with_image_license: 965
players_with_image_source_url: 966
review_items: 283
filled_image_commons_title_cells: 73
filled_image_url_cells: 73
filled_image_author_cells: 966
filled_image_license_cells: 965
filled_image_source_url_cells: 966

A helper file was then produced:
players_image_metadata_enriched_dates_normalized.csv

This file normalized date_of_birth to YYYY-MM-DD format and is intended to be the working/final Step 4 players file after remaining manual fixes.

Additional audit/helper files produced during Step 4:
step4_pre_import_audit.csv
step4_image_review_with_context.csv
step4_identity_sanity_audit.csv
step4_current_remaining_issues.csv

A validation script was also generated:
validate_player_identity_against_wikidata.py

It was run and produced:
player_identity_validation.csv
player_identity_validation_review_queue.csv
player_identity_validation_summary.csv

The validation script is read-only. It does not modify the players file. It checks:
display name vs Wikidata label/aliases
local DOB vs Wikidata DOB
footballer/sport signals
national team / citizenship context
club vs Wikidata P54 as a soft warning
age plausibility

Important caveat:
Wikidata is often incomplete or stale for current club, birthplace, and sometimes DOB. If a row has manual verification noted in the notes column, treat that manual review as higher authority than automated validation warnings. The validation script is a risk-ranking tool, not the final authority.

Known Step 4 image/license decisions:

Tarik Muharemovic:
His Commons/Wikimedia page was missing a license. Recommendation was to clear all five image fields for now:
image_commons_title
image_url
image_author
image_license
image_source_url

Attribution-only rows manually checked by the user:
Nadir Benbouali — Attribution — mlsz.hu – Hungarian Football Federation
Raphinha — Attribution — Govern de Catalunya
Mehdi Torabi — Attribution — Student News Agency
Sadio Mané — Attribution — خبرگزاری ورزش ایران - ایپنا (Iran Pro Sport News Agency - IPNA)
Kenan Yildiz — Attribution — mlsz.hu – Hungarian Football Federation
Merih Demiral — Attribution — mlsz.hu – Hungarian Football Federation

GFDL rows manually checked:
Joshua Brenet — GFDL 1.2
Jurgen Locadia — GFDL 1.2

The user also manually corrected 65 players whose birth_country had been set to United Kingdom. These should now be corrected to the relevant constituent country, such as England, Scotland, Wales, or Northern Ireland. If a newly uploaded/latest file still shows birth_country = United Kingdom, flag that the wrong file may have been exported or those edits were not preserved.

Amirhossein Mahmoudi:
The player lacks a Wikidata page. Previously he had an incorrect QID and impossible date. The correct handling is:
wikidata_id = blank
bio_source_url = reliable non-Wikidata source
data_confidence = verified_non_wikidata_source
manual_review_flag = FALSE
notes = No Wikidata item found; manually verified from source.
Clear image fields if they came from the wrong QID.

Before moving on, if the user provides a latest players file, verify:

1. 1,248 rows, one per player.
2. player_id unique.
3. no duplicate wikidata_id values except blanks.
4. date_of_birth is YYYY-MM-DD.
5. no impossible birth years.
6. Tarik Muharemovic has no unlicensed image.
7. Amirhossein Mahmoudi has no wrong QID/date.
8. birth_country does not still contain United Kingdom if the user intended constituent-country specificity.
9. image rows with image_url also have image_license and image_source_url unless intentionally blank/deferred.
10. manually reviewed identity warnings are reflected in notes/manual_review_flag/data_confidence.

What still needs to be done:

STEP 5 — Normalize clubs

This is the next major task.

Old clubs.csv was generated from raw club names and had about 511 rows. It was not fully normalized. Because the players list underwent heavy vetting and modifications, clubs.csv needs to be regenerated using a new script. The goal is to collapse naming variants, assign stable club identities, fill club metadata, and prepare for geocoding.

Inputs likely needed:
latest players file from Step 4 (included in the players sheet of world_cup_2026_player_map_master.xlsx, which is the downloaded version of the master Google Sheets document which we're assembling)
step2_outputs/clubs.csv (attached, unvetted)
step2_outputs/player_club_at_callup.csv (attached, unvetted)
step2_outputs/squad_entries.csv (attached, unvetted)
possibly raw_roster_import.csv (included in world_cup_2026_player_map_master.xlsx)

Tasks:

1. Audit club_name_raw / club_name variants.
2. Identify duplicate or equivalent clubs caused by abbreviations, translations, spelling, suffixes, punctuation, or source inconsistencies.
3. Decide the canonical club_name for each club.
4. Assign or verify club Wikidata QIDs where possible.
5. Preserve internal club_id stability where possible. If merging duplicate clubs, update player_club_at_callup.club_id to the chosen canonical club_id.
6. Create a club normalization review queue for ambiguous cases.
7. Fill or prepare columns:
   wikidata_id
   club_name
   club_name_ascii
   country
   league
   city
   stadium
   club_source_url
   geo_source
   manual_review_flag
   notes

Important:
Do not geocode until club normalization is complete. Otherwise the same club may be geocoded multiple times under different names.

The recommended output files for Step 5:
clubs_normalized.csv
player_club_at_callup_club_normalized.csv
club_normalization_review_queue.csv
club_normalization_summary.csv
club_alias_map.csv

Useful logic:
Club matching should use name normalization, fuzzy matching, Wikidata candidate matching, and possibly league/country context. It should not auto-merge uncertain matches. Route uncertain cases to a manual review queue.

Potential controlled values:
manual_review_flag = TRUE/FALSE
club_source_url = Wikidata URL or official club source
geo_source = blank until Step 6
notes = include merge decisions, aliases, or uncertainty

For each generated output file from the scripts given to the user, include a brief explanation of what the file is for and what the user should do with it.

STEP 6 — Geocode only after club normalization

After clubs are normalized, geocode unique clubs, not player rows.

Recommended map location rule:
For public football mapping, prefer home stadium coordinates where available.
If stadium coordinates are unavailable, use club city coordinates.
Avoid headquarters/training-ground coordinates unless explicitly chosen.

Tasks:

1. For each normalized club, fetch/derive:
   country
   league
   city
   stadium
   club_lat
   club_lon
   geo_source
   club_source_url
2. Prefer Wikidata for stadium/city/coordinate data where reliable.
3. If Wikidata is missing or wrong, use a consistent external geocoder or manual verification.
4. Produce a geocoding review queue for missing/ambiguous/low-confidence coordinates.
5. Do not geocode duplicate aliases; only geocode canonical clubs.

Potential outputs:
clubs_geocoded.csv
club_geocoding_review_queue.csv
club_geocoding_summary.csv

Potential validation:
club_id unique
club_name nonblank
club_lat and club_lon valid decimal degrees
no impossible coordinates
every player_club_at_callup.club_id exists in clubs_geocoded.club_id
markers visually plausible if plotted

STEP 7 — Build daily update snapshots

This is the maintenance/update workflow. It matters because World Cup rosters can change due to injury, illness, replacement rules, and late announcements.

Goal:
Build a reproducible snapshot/diff system so updates can be detected and recorded without silently overwriting the dataset.

Tasks:

1. Create a snapshots folder structure, e.g.:
   snapshots/YYYY-MM-DD/raw_roster_import.csv
   snapshots/YYYY-MM-DD/players.csv
   snapshots/YYYY-MM-DD/squad_entries.csv
   snapshots/YYYY-MM-DD/clubs.csv
   snapshots/YYYY-MM-DD/player_club_at_callup.csv

2. Build or plan a script that compares the latest official/bootstrap source output against the previous snapshot.

3. Detect changes such as:
   new player added
   player removed
   player replaced
   squad_status changed
   club changed
   shirt number changed
   position changed
   source URL changed
   bio/image corrections
   manual overrides

4. Write differences to change_log, not just overwrite fields.

5. Maintain squad_status values such as:
   active
   removed
   replaced
   withdrawn
   provisional
   standby
   uncertain

6. Make sure replacements are represented with:
   is_replacement
   replaced_player_id
   replacement_reason
   source_url
   verified_at

Potential outputs:
change_log_updated.csv
snapshot_diff_report.csv
manual_review_queue_updates.csv
updated_squad_entries.csv
updated_players.csv

Important:
The daily update process should be designed so the public dashboard can show “last updated” and possibly “recent changes” or “roster changes since previous snapshot.”

Next-development note:

Steps 5, 6, and 7 are the planned next steps, but they are not rigid. We can add, remove, split, or reorder steps as needed. For example, we may add:
Step 5b: club Wikidata matching
Step 6b: stadium vs city coordinate review
Step 7b: dashboard-ready export files
Step 8: build first Streamlit/Folium/Plotly prototype
Step 9: build production web app with Leaflet/MapLibre
Step 10: deploy to a website/self-hosted environment

Likely final site architecture options:
MVP: Python + Streamlit + Plotly/Folium/PyDeck
More polished static/public site: Python data pipeline exports JSON/GeoJSON, frontend uses Leaflet or MapLibre
Full app: Next.js/React frontend, MapLibre/Leaflet map, static JSON or lightweight backend/Supabase/Postgres

Do not jump straight to site code until clubs are normalized and geocoded, unless building a prototype with placeholder coordinates.

Core project rules:
Do not append duplicate players; replace/update by player_id.
Do not change player_id.
Do not use Wikidata QID as the primary key.
Do not trust Wikidata blindly over manually vetted sources.
Do not use random web images. Use Commons or manually verified reusable images only.
Do not silently overwrite roster changes; write them to change_log.
Do not geocode before club normalization.
Keep all outputs audit-friendly and reproducible.

Immediate next action in the new chat:
If not already attached/present, ask the user to upload or identify the latest finalized Step 4 players file plus Step 2 clubs/player_club_at_callup/squad_entries files if needed, then perform a quick pre-Step-5 audit and begin club normalization.
