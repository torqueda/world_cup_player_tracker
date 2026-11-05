#!/usr/bin/env python3
"""
Register the two datasets the Analysis pages use in the workbook's sources sheet.

The "What goes with winning" and "Who has a photo" pages read files written by
scripts/analysis/, which use two outside datasets:

- martj42's international results, for the Elo ratings
  (data/raw/martj42_results_snapshot.csv.gz);
- transfermarkt-datasets, for squad market values
  (data/raw/transfermarkt_wc2026_snapshot.csv).

Both are CC0. This adds a sources row for each and one change_log row. Writes a
backup next to the workbook first (git ignores it). A second run changes
nothing.

Usage:
    python scripts/data_pipeline/apply_2026_11_analysis_sources.py
    python scripts/export/refresh_all_exports.py
"""

from __future__ import annotations

import shutil
from datetime import date

from openpyxl import load_workbook

from apply_2026_11_data_fixes import FIX_DATE, REPO_ROOT, WB_PATH, Sheet, change_row, text

CHANGE_ID = f"chg_{FIX_DATE}_analysis_sources"

# source_id, source_type, publisher, url, title, accessed_at, published_at, reliability_tier, notes
ANALYSIS_SOURCES = (
    (
        "martj42_international_results", "historical_results", "martj42 on GitHub",
        "https://github.com/martj42/international_results",
        "International football results from 1872", FIX_DATE, None, "secondary",
        "Every men's international result since 1872, with former team names, for the Elo ratings that "
        "scripts/analysis/team_strength.py builds and the win factors. Snapshots: "
        "data/raw/martj42_results_snapshot.csv.gz and data/raw/martj42_former_names_snapshot.csv. "
        "Licence: CC0.",
    ),
    (
        "transfermarkt_datasets", "market_values", "dcaribou/transfermarkt-datasets on GitHub",
        "https://github.com/dcaribou/transfermarkt-datasets",
        "transfermarkt-datasets: players and player valuations", FIX_DATE, None, "secondary",
        "Player market values, from the players and player_valuations tables (valuations to 2026-06-12), "
        "for the squad value factor and the photo analysis. Only values set in the 12 months before the "
        "tournament are used. Snapshot: data/raw/transfermarkt_wc2026_snapshot.csv. Licence: CC0.",
    ),
)


def main() -> None:
    wb = load_workbook(WB_PATH)
    sources = Sheet(wb["sources"])
    change_log = Sheet(wb["change_log"])

    existing = {text(sources.get(row, "source_id")) for row in sources.rows()}
    added = [entry for entry in ANALYSIS_SOURCES if entry[0] not in existing]
    logged = {text(change_log.get(row, "change_id")) for row in change_log.rows()}
    if not added and CHANGE_ID in logged:
        print("Nothing to change: both sources are already registered.")
        return

    for entry in added:
        sources.ws.append(list(entry))
    if CHANGE_ID not in logged:
        change_log.ws.append(change_row(
            CHANGE_ID, "ALL", None, "bulk_update", "sources rows", None,
            "added: " + ", ".join(entry[0] for entry in ANALYSIS_SOURCES), None,
            "Registered the two datasets behind the new Analysis pages: martj42's international results, "
            "for the Elo ratings, and transfermarkt-datasets, for squad market values. Both are CC0.",
        ))

    backup = WB_PATH.with_name(f"{WB_PATH.stem}.backup_{date.today().isoformat()}_analysis_sources.xlsx")
    shutil.copy2(WB_PATH, backup)
    print(f"Backup written: {backup.relative_to(REPO_ROOT)}")
    wb.save(WB_PATH)
    verify_saved_workbook()
    print(f"Registered {len(added)} sources; saved {WB_PATH.relative_to(REPO_ROOT)}")


def verify_saved_workbook() -> None:
    """Read the saved file back and check both rows and the change_log row."""
    wb = load_workbook(WB_PATH)
    sources = Sheet(wb["sources"])
    for entry in ANALYSIS_SOURCES:
        row = sources.find("source_id", entry[0])
        if text(sources.get(row, "url")) != entry[3]:
            raise SystemExit(f"sources {entry[0]}: the row did not save")
    Sheet(wb["change_log"]).find("change_id", CHANGE_ID)


if __name__ == "__main__":
    main()
