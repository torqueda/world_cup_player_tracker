# Decision log

Newest first. Each entry gives the date, the decision, the options that were on the table, and why. Add an entry in the same pull request as the change it decides. Decisions made before this log started are recorded in [roadmap_to_deployment.md](roadmap_to_deployment.md) and [dataset_finalization_report_2026-07-12.md](dataset_finalization_report_2026-07-12.md).

## 2026-11-05: Keep per-page data loading on hold

- **Decision:** the site keeps loading all of its data in one bundle for now, and the PRD sets no speed target yet.
- **Options:** load each page's data on demand now, or after the other fixes are live.
- **Why:** the other changes are reviewed on the live site first. The speed target is set when this change is taken up, against measurements made then.

## 2026-11-05: Replace hand-typed counts on Home

- **Decision:** the two counts on Home ("Roughly 500 player records..." and "About 300 more...") are replaced by counts computed from the pipeline's own files: its review queues where they support a count, otherwise the stage-by-stage counts of how players were matched.
- **Options:** keep the counts, soften the wording, or compute them.
- **Why:** no file in the repo backs the current counts, and the PRD promises that every number on the site is computed from the data.

## 2026-11-05: Confirm each suspected wrong-person match by hand

- **Decision:** the players whose identity match looks wrong are listed with their evidence in the data-fix pull request, and each one is confirmed or rejected there before the data changes.
- **Options:** fix them automatically, or check each one first.
- **Why:** the evidence is indirect (cached Wikidata facts that disagree with Wikipedia's squads), so a person checks each one.

## 2026-11-05: Keep the Wikimedia Commons player photos

- **Decision:** the site keeps showing Commons photos, and the roadmap is corrected.
- **Options:** keep the photos and correct the roadmap, or drop the photos as the roadmap said on 2026-07-12.
- **Why:** the site already shows a photo for 965 of 1,275 players, and the planned photo analysis needs them.

## 2026-11-05: Split Analysis into sub-pages

- **Decision:** Analysis becomes a short index plus one page per question: squad make-up, clubs and leagues, players, and matches and venues, with the two-team comparison as its own tool.
- **Options:** keep one long page, or split it.
- **Why:** the page is more than 9 laptop screens long and answers five unrelated questions.

## 2026-11-05: Fonts

- **Decision:** IBM Plex Sans for body text in place of Inter, and IBM Plex Mono for headings and table figures on every page except Home, whose headings keep Archivo. The fonts are served from the site instead of Google Fonts.
- **Options:** keep Inter and Archivo; IBM Plex Sans everywhere; Plex Sans with Plex Mono headings.
- **Why:** to give the site a look of its own; Inter set 85% of the text. Keeping Archivo on Home only lets the two heading faces be compared on the live site.

## 2026-11-05: Non-goals

- **Decision:** the project will not support betting, and the site and pipeline will not be packaged or sold as a product. It also shows no live or post-tournament data, and no forecast as fact.
- **Options:** leave the scope open, or state it.
- **Why:** the project is a free public reference built from public sources (see Problem and readers in [prd.md](prd.md)), and stating the scope keeps later additions inside it.
