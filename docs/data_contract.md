# Data contract

Status: outline, 2026-11-05. The machine-readable contract and its test come in a later pull request; until then this file is the plan.

The site imports the JSON exports in `data/processed/app_exports/` and trusts their shape. Today a renamed or missing workbook column blanks part of a page instead of failing a build. The contract states, for each exported table, what the site may rely on. A test checks every exported row against it, and the site's TypeScript types are generated from it.

## What each entry holds

- **key:** the field that identifies a row, unique and never empty.
- **fields:** for each field, its type (string, integer, number, boolean, date, enum or list), whether it is required, and its allowed values or pattern.
- **read_by:** the pages that read the table.
- **notes:** units, the source, and known gaps.

## Where it will live

- `data/contract/exports.yaml`: one entry per exported table. PyYAML is added to the dev requirements to read it.
- `tests/test_data_contract.py`: checks every row of every export against the contract. It runs in CI with the other pytest tests.
- `scripts/export/generate_site_types.py`: writes `site/src/lib/data/types.ts` from the contract. CI fails if the committed file differs from what the script writes.
- The contract becomes the data dictionary, replacing the workbook's `data_dictionary` sheet, which describes 4 of the other 12 sheets.

## Exported tables

Row counts are from the export of 2026-08-20. The contract starts with the three tables the site reads most (players, squad entries and player statistics) and grows from there.

| Export | Rows | Key | Read by the site |
|---|---|---|---|
| `players` | 1,275 | `player_id` | Yes |
| `squad_entries` | 1,275 | `squad_entry_id` | Yes |
| `player_club_at_callup` | 1,275 | `player_club_callup_id` | Yes |
| `player_stats` | 1,231 | `player_id` | Yes |
| `clubs` | 461 | `club_id` | Yes |
| `cities` | 397 | `city_key` | Yes |
| `referees` | 167 | `official_id` | Yes |
| `matches` | 104 | `match_id` | Yes |
| `club_aliases` | 49 | `alias` | Yes |
| `teams` | 48 | `team_code` | Yes |
| `team_stats` | 48 | `team_code` | Yes |
| `coaches` | 48 | `coach_id` | Yes |
| `change_log` | 11 | `change_id` | Yes, on Methodology |
| `sources` | 10 | `source_id` | No |
| `confederations` | 6 | `code` | Yes |
| `meta` | one object | none | Yes |
| `manual_review_queue` | 0 | to be set | No |
| `world_cup_history` | 104 | `match_id` | No: a copy of `matches`, to be removed |

## Example entry

Written from what `players.json` holds today: all 1,275 IDs match the pattern below, every birth date is a 19-character date-time string, and 1,274 players have a Wikidata ID.

```yaml
players:                               # data/processed/app_exports/players.json
  key: player_id
  fields:
    player_id:        {type: string, required: true, pattern: "^p_[a-z]{3}_[a-z0-9_]+_[0-9a-f]{8}$"}
    display_name:     {type: string, required: true}
    date_of_birth:    {type: string, required: true, format: "YYYY-MM-DDT00:00:00"}
    primary_position: {type: enum, values: [goalkeeper, defender, midfielder, forward]}
    wikidata_id:      {type: string, pattern: "^Q[0-9]+$", required: for active players}
    match_method:     {type: enum, values: [auto, dob, manual]}   # planned: how the identity match was settled
  read_by: []                         # the pages that import it, listed from the site code when the contract is written
```

## Rules

- A pull request that changes an export changes the contract in the same change.
- A new field starts as optional. It becomes required once every row has it.
- Removing a field or narrowing its allowed values needs a line in [decision_log.md](decision_log.md).
