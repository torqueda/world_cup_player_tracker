# Site Content & Skills-Showcase Proposals

Written 2026-07-12, after the final-dataset import and the site's expansion to seven routes
(Overview, Players & Clubs, National Teams, Matches, Stats, Insights, Data & Sources).
Part 1 proposes content built on the newly collected data (stats, matches, coaches,
referees, caps, captains). Part 2 proposes additions chosen specifically to demonstrate
data science/analysis, AI/product management, and general engineering skills — each one
maps to a portfolio talking point.

---

## Part 1 — New and refined page content

### Already implemented this pass (baseline to build on)

- **Matches**: all 100 results by stage with penalty shootouts, upcoming semifinal/final cards.
- **Stats**: Golden Boot race, assists, minutes, discipline leaders; full team table
  (P/W/D/L/GF/GA, stage reached, xG, possession); goalkeeper-saves slot reserved until the
  GK columns are imported.
- **National Teams**: coach line, stage reached, captain badge, shirt numbers, pre-tournament caps.
- **Insights**: donut gauges for home-grown vs diaspora squads, team explorer on the left with
  coach + stage context.
- **Data & Sources**: source registry with reliability tiers, change log, method notes.

### Highest-value additions next (data already in hand)

1. **Player detail panel (click any player anywhere).** One overlay/panel with: name, team,
   shirt number, captain flag, position, DOB/age, birthplace, club + league, caps/goals before
   the tournament, and their tournament stat line (minutes, goals, assists, cards, GK saves).
   Every field already exists in the exports. This single feature makes the whole site feel
   "deep" — every name becomes a door instead of a dead end.
2. **Knockout bracket visual on Matches.** The match list already carries stages; an SVG
   bracket (R32 → Final) with clickable ties turns the page from a log into a story. Reserve
   the final/third-place slots that fill in after July 14–15.
3. **"Road to the final" on each National Team.** Filter `matches` by team: their group
   results, knockout run, and (from team_stats) xG vs goals. Fits in the existing detail panel.
4. **Referees page or Data & Sources section.** The 167 officials with roles, confederations,
   and (already scraped, in `wikipedia_match_officials.csv`) per-match assignments. Angle:
   "who refereed whom" — e.g., which confederation's referees officiated which teams.
   Low urgency, high completeness value.
5. **Coach angles on Insights.** Foreign vs native coaches (coach_nationality vs team),
   which coach nationalities are most in demand — one donut row + a chip list. All data present.
6. **Stats deltas after each refresh.** Because `as_of_stage` is stored, a refresh after the
   semifinals can show "+2 goals since QF" chips next to leaders. Cheap once the second
   snapshot exists (and the snapshot/diff design is already planned in the roadmap).

### Reserved-but-empty sections worth scaffolding now

- **Player images**: the player panel should render a framed placeholder with attribution
  space, so the license-free image drop-in later is a data change, not a layout change.
- **Birthplace map**: a second tab on Players & Clubs ("Where they play" / "Where they're
  from") — the UI toggle can ship disabled until birthplace geocoding lands.
- **Historical context** (`world_cup_history` expansion): a "2026 vs past Cups" section
  stub on Insights for post-tournament work.

---

## Part 2 — Skills-showcase additions

Each item lists the skill it demonstrates and the concrete artifact a reviewer would see.

### Data science & analysis

1. **xG over/under-performance analysis.** Teams' goals vs xG (both in `team_stats`) as a
   dumbbell/scatter with a short written interpretation ("Japan scored 8 from 3.17 xG — the
   tournament's biggest overperformance"). *Artifact: an Insights section that reads like a
   mini analysis memo, not just a chart.*
2. **Squad-value-free performance model.** A simple, transparent index (e.g., points per
   match, goal difference per xG, minutes-weighted squad age) combined into a ranked
   "tournament performance index" with the formula documented on the page. Shows modeling
   judgment without black boxes. *Artifact: methodology note + reproducible score.*
3. **Diaspora analysis deep-dive.** You already have birth country vs team; add club country
   as the third axis: sankey or matrix of born-in → plays-for → club-in. *Artifact: one
   genuinely novel visualization built from three joined tables you assembled yourself.*
4. **Data-quality dashboard.** Chart the pipeline's own health: match rates from each source
   join (e.g., 1,210/1,231 FIFA stat lines auto-matched, 21 hand-resolved), DOB mismatches
   caught, clubs pending geocode. *Artifact: turns your QA work into a visible strength —
   very few portfolio projects show their error budget.*

### AI / product management

5. **Decision log as a first-class doc.** You already have the raw material (checklists,
   change_log, the FIFA-permission decision record, the "dataset-first vs QA-first"
   reordering). Curate `docs/decision_log.md`: 10–15 dated decisions, each with context →
   options → choice → outcome. *Artifact: exactly what PM interviewers ask for ("walk me
   through a tradeoff you made").*
6. **AI-assisted workflow case study.** The `presentation/world_cup_tracker_ai_case_study_draft.md`
   is already started — finish it with concrete episodes: hybrid scraping decision, the
   browser-collection method for JS-rendered pages, reconciliation edge cases (Abughoush/Taha,
   Kim Tae-hyun vs Tae-hyeon), and where human review overrode automation. *Artifact: a
   credible "how I manage AI as a tool" narrative with receipts.*
7. **Metrics definition for the site itself.** Define success metrics (e.g., % of players
   with complete profiles, data freshness lag vs FIFA, search success rate after beta) and
   show them on an internal page. *Artifact: product thinking applied to your own product.*

### General coding / technical

8. **Code-split the bundle and publish the before/after.** The one flagged issue in every
   build: a 4 MB JS chunk. Route-level dynamic `import()` (already scoped in the deferred
   doc) plus a README note "3.4 MB → N chunks, first paint X% faster." *Artifact: a
   measurable performance PR.*
9. **Pipeline test suite.** A small pytest run in CI (GitHub Actions once the repo is pushed):
   export pipeline invariants (unique IDs, join integrity, 48×26 active rosters) + one
   snapshot test on `meta.json` counts. *Artifact: green CI badge + tests catching real
   regression classes you've actually hit (e.g., the SJK ascii drift).*
10. **One-command dataset refresh with diff report.** Wrap scrape → reconcile → merge →
    export into a single `make refresh` (or script) that ends by printing what changed
    vs the previous exports. *Artifact: demonstrates pipeline ergonomics; also what you'll
    genuinely need for the post-semifinal update.*
11. **Deployment with CI/CD.** GitHub Pages/Netlify auto-deploy on push, with the build
    running typecheck + tests first. *Artifact: a public URL and a professional release
    process, which is itself the portfolio piece.*

### Suggested order given the July 14 deploy

Pre-deploy (high value, low risk): player detail panel (1), bracket visual (2), code-split (8).
Deploy, then during the semis/final window: stats deltas (6), xG analysis (1 of Part 2), CI (9, 11).
Post-tournament: diaspora deep-dive, decision log, case study, the rest.
