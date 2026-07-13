# World Cup Tracker AI Case Study Draft

This version is written to balance executive/business framing with technical/build-process detail.

## Best Placement In The Overall Deck

**Best fit if the team can reorder sections:** place this segment **after** "Steps for Safe Deployment" and **before** "Redesigning Supply Chain Workflows with Agentic AI."

Why:
- It bridges the strategy/safety section to the supply-chain workflow section.
- It gives the audience one grounded example of what real AI work looks like before the conversation moves back into stronger automation and agentic workflows.
- It reinforces the message that trustworthy automation depends on trustworthy underlying data.

**If you are locked into presenting fourth:** frame this as the closing reality check.

Suggested transition:
`The earlier sections showed where AI is going. I want to show what the work feels like when you are still building the data foundation that those future workflows depend on.`

---

## Slide 1

**Title**

AI Helped Me Build Faster, But It Did Not Remove the Data Problem

**Structure**

- Clean title with one short subtitle
- Left side: 3 project facts
- Right side: one screenshot of the workbook tabs, project folders, or a review queue

**On-slide copy**

- 2026 World Cup player-club tracker project
- 1,248 players across 48 national teams
- Step 5 finished with 464 clubs, but the active Step 6 geocoding snapshot has 457 rows and still needs reconciliation

**Image ideas**

- Screenshot of the project folder showing `data/raw`, `data/processed`, and `scripts`
- Or a screenshot of the workbook tabs to show the relational structure

**Speaker notes**

This project is supposed to become a public World Cup map and dashboard, but the real work so far has been building trustworthy data rather than building the site itself. The dataset covers players, national teams, clubs, images, sources, and club locations. That is why I think it works as an AI case study even without a polished demo. The biggest lesson has been that AI can help me move faster, but it does not remove the underlying problem when the data is messy, incomplete, or inconsistent.

---

## Slide 2

**Title**

Why A Sports Dataset Still Fits An Enterprise AI Discussion

**Structure**

- Two-column layout
- Left column: "This Project"
- Right column: "Enterprise / Supply Chain Equivalent"

**On-slide copy**

- Player identity matching -> supplier, item, or customer identity matching
- Club normalization -> master data cleanup across systems
- Roster changes and source tracking -> operational audit trails and change logs

**Image ideas**

- No image needed
- If you want one, use a simple comparison arrow between the two columns

**Speaker notes**

Even though the subject is sports, the underlying problem is very familiar to enterprise teams. I am matching entities across inconsistent sources, standardizing names, preserving stable IDs, and deciding when an automated suggestion is safe enough to accept. In supply chain or finance, the same pattern shows up in supplier data, site data, product data, and operational exceptions. The domain is different, but the AI lesson is the same: if the underlying records are not reliable, downstream automation becomes fragile very quickly.

---

## Slide 3

**Title**

What The Workflow Actually Looked Like

**Structure**

- Horizontal 5-step process
- One short line per step
- Add one callout at the bottom: `Most of the time went into validation, not generation.`

**On-slide copy**

- Scrape and correct roster source data
- Generate stable relational IDs
- Match players to Wikidata
- Pull Commons image metadata
- Normalize clubs, then geolocate them through review queues

**Image ideas**

- Simple pipeline diagram
- Or a collage of 3 CSV screenshots: raw import, review queue, final summary

**Speaker notes**

The project moved through a series of data-building stages rather than one big AI task. First I scraped and corrected the roster source. Then I generated stable IDs so the workbook could behave more like a relational database than one flattened spreadsheet. After that I used AI-assisted scripts and external data sources to match players, collect image metadata, normalize club names, and begin club geolocation. Every step created useful output, but every step also created another validation problem that still needed human review.

---

## Slide 4

**Title**

Prompt Design Became Part Of The Workflow

**Structure**

- Left side: "Long context prompt"
- Right side: "Step-specific prompt"
- Bottom row: "Tradeoffs"

**On-slide copy**

- Long context prompts made new chats more reliable
- Step-specific prompts narrowed the task and reduced ambiguity
- The downside: they took time to write, revise, and maintain

**Image ideas**

- Screenshot of the two prompt examples you attached
- Highlight sections like goals, schema, rules, completed steps, and current task

**Prompt characteristics to mention**

- The long project-context prompt acts like a reusable handoff packet: project goal, schema, rules, completed steps, and next steps
- The Step 6 prompt narrows the task further: file authority, row counts, match-status meanings, approval fields, and output expectations
- Together, they reduce re-explaining and make transitions between chats smoother

**Prompt drawbacks to mention**

- They take real time to draft and revise
- They consume a meaningful part of the context window
- They can preserve stale assumptions if counts, filenames, or workflow status changes

**Speaker notes**

One thing I did not expect is that prompt writing itself became part of the project workflow. When I had to restart in a new chat, the longer context prompt made the handoff much smoother because it gave the model the project goal, the data model, the rules, and the current status. Then the Step 6 prompt narrowed the task even more by defining row counts, review statuses, output files, and approval rules. That helped the model behave more consistently, but there was a real cost. These prompts took time to draft, they used up context space, and they could become stale if the latest files or counts changed.

---

## Slide 5

**Title**

Where AI Added Real Value

**Structure**

- Three stacked sections
- Each section gets one short headline and one example

**On-slide copy**

- Scaffolding scripts and repeatable transforms
- Generating candidate matches and review queues
- Turning vague cleanup work into explicit operating rules

**Prompt examples to show**

- "Generate a script that assigns stable internal IDs for players, clubs, and join tables. Do not use external IDs as primary keys."
- "Create a Wikidata matching workflow that scores candidates and routes uncertain rows to a manual review queue instead of forcing a match."
- "Normalize club naming variants, but never auto-merge ambiguous clubs without a review file."

**Image ideas**

- Screenshot of one script and one summary CSV
- Or side-by-side of a prompt and the resulting structured output

**Speaker notes**

AI was most useful when I treated it like a systems assistant instead of an answer engine. It helped scaffold scripts, define output files, propose matching logic, and create review queues so I did not have to inspect everything from scratch. That mattered because the project is too large for purely manual work, but still too messy for full automation. The best results came when I asked AI to create structure, checks, and candidate sets instead of asking it to declare final truth.

---

## Slide 6

**Title**

Where AI Was Wrong, Overconfident, Or Just Created More Work

**Structure**

- Three columns: `Ambiguity`, `False confidence`, `Review burden`
- Use one concrete project example under each

**On-slide copy**

- 1,152 player rows auto-matched, but some high-confidence matches still had to be corrected manually
- Step 6 generated 4,592 club candidate rows for 457 clubs and still left 251 review rows
- Some club candidates were clearly the wrong entity: places, rivers, constituencies, or women's teams instead of the men's football club

**Image ideas**

- Screenshot of `club_geocoding_review_queue.csv`
- Good wrong-result examples:
  - `Charleroi` matched to a borough in Pennsylvania
  - `Violette` matched to a river in France
  - `Wrexham` matched to constituencies, a city, and the women's team
- Optional second image:
  - a player identity or image-cleanup example such as Tarik Muharemovic or Amirhossein Mahmoudi

**Speaker notes**

This was the most important lesson for me. AI outputs can look organized and convincing while still being wrong in ways that are easy to miss. In this project, same-name players caused bad identity matches, and club searches often returned the wrong kind of entity entirely. The failure mode was not random nonsense. It was plausible nonsense, which is much harder to catch. AI also created a second bottleneck by producing large candidate sets that still had to be reviewed manually before they could be trusted.

---

## Slide 7

**Title**

What I Would Carry Into Supply Chain, Finance, Or Marketing

**Structure**

- Strong title
- Four short recommendations
- One closing line at the bottom

**On-slide copy**

- Use AI first for parsing, matching, summarizing, and queue triage
- Do not start with full autonomy on messy operational data
- Build audit trails before you build agents
- Keep humans in the loop for exceptions and approvals

**Closing line**

If the data foundation is weak, AI scales confusion faster than it scales value.

**Image ideas**

- No image needed

**Speaker notes**

My takeaway is that AI is already useful for enterprise data work, but mostly in the parts of the process where speed matters more than final authority. It can read, classify, compare, summarize, and draft much faster than a person. What it still cannot do reliably is remove ambiguity from messy operational reality on its own. For supply chain, finance, and similar teams, the first win is usually not full autonomy. The first win is better candidate generation, better exception handling, and better review workflows built on top of data that people trust.

---

## Visual Suggestions From Your Real Project

These are good candidate screenshots because they support your story and are grounded in the files:

- A raw source error or source-variant example:
  - `Tottehham` vs `Tottenham Hotspur`
  - `Kasimpasa` vs `Kasımpaşa`
  - `Çaykur Rizespor` vs `Çaykur Rizespor`
- A player/data-review example:
  - Tarik Muharemovic image-license cleanup
  - Amirhossein Mahmoudi with no Wikidata item and a manual-source fallback
  - Ali Yousef / Ali Yousif repair as an example of source spelling vs relational stability
- A geocoding false-positive example:
  - `Charleroi`
  - `Violette`
  - `Wrexham`

---

## Fact-Check Notes

These are the project-backed claims in this draft and where they came from.

- `1,248 players / 48 national teams / current data-build phase`
  - [README.md](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/README.md:1)
- `Step 5 final clubs = 464`
  - [step5_final_summary.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/club_normalization_final/step5_final_summary.csv:1)
  - [README_step5_final_outputs.md](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/club_normalization_final/README_step5_final_outputs.md:1)
- `Active Step 6 working snapshot = 457 club rows`
  - [README.md](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/README.md:102)
  - [pasted-text.txt](/Users/tomasorqueda/.codex/attachments/62051909-378e-41f5-96f3-73597304f6e9/pasted-text.txt:1)
- `1,152 player auto-matches / 96 needs review / 42 no match / 2,734 candidate rows`
  - [wikidata_match_summary.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/player_wikidata_matching/wikidata_match_summary.csv:1)
- `966 players with image URL / 965 with image license / 283 review items`
  - [image_metadata_summary.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/image_metadata/image_metadata_summary.csv:1)
- `14 high identity-review items / 73 medium / 612 low warnings / 549 ok`
  - [player_identity_validation_summary.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/identity_validation/player_identity_validation_summary.csv:1)
- `Step 6 candidate counts: 4,592 candidate rows / 457 clubs / 251 review rows / 8 no-candidate-or-failure rows`
  - [step6_match_summary.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/club_geolocation_working/step6_match_summary.csv:1)
- `Wrong-entity club examples such as Charleroi, Violette, and Wrexham`
  - [club_geocoding_review_queue.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/processed/club_geolocation_working/club_geocoding_review_queue.csv:1)
- `Source/canonical name-cleanup examples such as Tottehham, Kasimpasa, and Çaykur Rizespor`
  - [raw_roster_import_corrected.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/raw/raw_roster_import_corrected.csv:993)
  - [raw_roster_import_corrected.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/raw/raw_roster_import_corrected.csv:410)
  - [raw_roster_import_corrected.csv](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/data/raw/raw_roster_import_corrected.csv:284)
  - [normalize_clubs_step5.py](/Users/tomasorqueda/Downloads/CMU/Syllabi/Projects/GitHub/world_cup_player_tracker/scripts/club_normalization/normalize_clubs_step5.py:25)
- `Prompt characteristics and drawbacks`
  - Backed by your two attached prompt examples:
    - [Project-context prompt](/Users/tomasorqueda/.codex/attachments/afcb2b9f-eb3e-43d3-bf97-76d058d35fef/pasted-text.txt:1)
    - [Step 6 prompt](/Users/tomasorqueda/.codex/attachments/62051909-378e-41f5-96f3-73597304f6e9/pasted-text.txt:1)
  - The benefit/cost interpretation is an inference from prompt length, structure, and workflow use, not a measured repo metric.

---

## One Content Caution

One claim I would avoid making too strongly is that the club count is already fully settled. Your own project files show a real unresolved mismatch:

- Step 5 final import-ready clubs: 464
- Current Step 6 working snapshot: 457

That is not a weakness for the presentation. It is actually one of your strongest examples of why AI-assisted workflows still need reconciliation and manual approval before people start trusting the output.
