# World Cup 2026 Player Tracker: product requirements

Last updated 2026-11-05.

This file says what the site is for, what it promises its readers, and what is out of scope. A pull request that changes what the site shows, or what it says about itself, updates this file in the same change. Decisions and their reasons are in [decision_log.md](decision_log.md). The shape of the exported data is in [data_contract.md](data_contract.md).

## Problem and readers

Fans and analysts want to see where the 2026 World Cup players come from, which clubs and leagues supplied them, and what happened in the tournament, with every number traceable to a public source.

## Goals

- Show every player of the 48 final squads with club, birthplace and tournament statistics.
- Explain the squads, clubs and matches with a small set of analyses, each answering one question.
- Show how the data was collected and checked.

## Non-goals

- **Live or post-tournament data.** The dataset is final as of its export date.
- **Forecasts presented as fact.** Any model output is labelled as a model, with its method and how far off it was.
- **Commercial use.** The site is not built to support betting, and the site and pipeline are not packaged or sold as a product.

## Promises to readers, and the check behind each

Every sentence the site says about itself should trace to a row here.

| Promise | Check | In place |
|---|---|---|
| Every number on the site is computed from the exported data | Site unit tests; no hand-typed figures in page text | Partly: two counts on Home are typed by hand and will be replaced |
| Every player is the right person | Strict export audit; birth dates compared with Wikipedia's final squads; goals and cards compared across sources; a short review queue for doubtful identity matches | The audit, yes; the comparisons and the review queue arrive with the data fixes |
| Tables agree with each other | `tests/test_export_invariants.py` and cross-table tests | Invariants, yes; cross-table tests arrive with the site fixes |
| Every source is credited | The `sources` registry lists every source the pipeline uses, and the site's source list matches it | No: the registry lists only Wikipedia and FIFA today |
| Corrections after launch are logged with date and reason | A `change_log` row in the same change | Yes |
| The site's description of its own methods matches the code | Reviewed in any pull request that changes a pipeline script | After the site fixes, which correct the method notes |

## Pages

Each page has one name, used in the menu and as its heading, and answers one question. A new page or section needs a line here first. Addresses stay as they are so old links keep working.

| Page | Address | Question it answers |
|---|---|---|
| Home | `/` | What is this dataset, and what is in it? |
| Club Map | `/players-clubs` | Where are the clubs the players were called up from? |
| Squads | `/national-teams` | Who is in each squad? |
| Matches | `/matches` | What happened in each match? |
| Leaders | `/stats` | Who led the tournament statistics? |
| Analysis | `/insights` | An index of the analysis pages (below) |
| Methodology | `/sources` | How was the data collected and checked? |

**Analysis is split into sub-pages**, each 2 to 4 laptop screens long: squad make-up, clubs and leagues, players, matches and venues, and the two-team comparison as its own tool. Two more are planned: what makes a team more likely to win a match, and which players have a photo on Wikimedia Commons.

**Open naming question:** the Methodology page's heading reads "Data & sources". One name is chosen when the pages are rearranged.

## Quality bar for any change

- No axe WCAG 2.2 A or AA failures on any page at 390 px and 1440 px wide.
- Running text no wider than `--measure` (52 characters). Wide boxes are for tables, charts and maps.
- Typecheck, site unit tests, pytest and the strict export audit pass in CI.
- Speed: no target yet. One is set when per-page data loading is taken up.

## Decisions

See [decision_log.md](decision_log.md).

## Next

1. **Fix what the post-launch review found**, in this order:
    1. Site fixes: accessibility, phone layout, the text measure, the Methodology page's method notes, map tiles, and cross-table tests.
    2. Pipeline and repo cleanup: unused code and files removed, the Wikimedia contact read at run time, and the site's unit tests added to CI.
    3. Data fixes, each with a `change_log` row and its evidence, including a match-method field in place of stale match labels.
    4. The data contract, checked by pytest, with the site's types generated from it.
    5. Site copy, fonts, page arrangement and the Analysis split.
2. **Then add data and analyses:** team strength and history (Elo ratings, FIFA ranking, past results), line-ups and squad market values; match forecasts, labelled as a model; what makes a team more likely to win; and which players have a photo on Wikimedia Commons.

**On hold:** loading each page's data on demand instead of in one bundle.
