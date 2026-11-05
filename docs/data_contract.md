# Data contract

The site imports the JSON exports in `data/processed/app_exports/` and trusts their shape. The data contract states, for each export, what the site may rely on, so a renamed or missing workbook column fails the tests instead of blanking part of a page.

## Where it lives

- [`data/contract/exports.yaml`](../data/contract/exports.yaml): one entry per export, with every field's type, whether it can be null, and its allowed values, format, pattern and references. The comment at the top of the file explains each key.
- [`tests/test_data_contract.py`](../tests/test_data_contract.py): checks every row of every export against the contract. Each row must have exactly the contract's fields, in order. Keys must be unique and present, and every reference must point at a row that exists. It runs in CI with the other pytest tests.
- [`scripts/export/generate_from_contract.py`](../scripts/export/generate_from_contract.py): writes the site's TypeScript types (`site/src/lib/data/types.ts`) and the [data dictionary](data_dictionary.md) from the contract. The test fails when either committed file differs from what the script writes.

`meta.json` is a single object of counts rather than a table, so it has no entry; `tests/test_export_invariants.py` checks its counts against the files.

## Rules

- A pull request that changes an export changes the contract in the same change, then reruns the script.
- A new field starts with `nullable: true`. It loses it once every row has a value.
- Removing a field or narrowing its allowed values needs a line in [decision_log.md](decision_log.md).

## Known gaps

The contract describes the data as it is, including a few inconsistencies, so that they are visible and do not get worse:

- The tournament is spelled two ways: `fifa_world_cup_2026` in `teams` and in 1,248 rows of `squad_entries`, and `FIFA World Cup 2026` in the other 27 squad entries, `matches`, `player_stats` and `team_stats`.
- `change_log.changed_at` has one value with a midnight time, and `players.date_of_birth` and `matches.match_date` all have one, which the workbook export adds.
- Several fields are always empty because they were planned and never collected: `players.fifa_id`, `espn_id`, `birth_lat`, `birth_lon` and `height_cm`; `squad_entries.replaced_player_id`; `player_club_at_callup.parent_club_id` and `loan_club_id` (and `is_on_loan` is always `unknown`).
