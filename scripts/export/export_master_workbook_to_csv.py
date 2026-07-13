#!/usr/bin/env python3
"""
Export the current master workbook sheets to canonical CSV snapshots.

These CSVs are meant to be the current file-based counterparts of the workbook
for downstream scripts and dashboard work. Historical step-specific outputs stay
in their original folders for provenance.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from workbook_rows import list_sheet_names, read_sheet_rows

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SHEETS = [
    "players",
    "squad_entries",
    "clubs",
    "player_club_at_callup",
    "sources",
    "change_log",
    "manual_review_queue",
    "world_cup_history",
    "match_history",
    "player_stats",
    "team_stats",
    "coaches",
    "referees",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--master-workbook",
        default=str(REPO_ROOT / "data/master/world_cup_2026_player_map_master.xlsx"),
        help="Current master workbook.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data/processed/master_exports"),
        help="Directory for canonical CSV snapshots.",
    )
    parser.add_argument(
        "--sheets",
        nargs="*",
        default=DEFAULT_SHEETS,
        help="Workbook sheets to export.",
    )
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    args = parse_args()
    workbook_path = Path(args.master_workbook)
    output_dir = Path(args.output_dir)
    available_sheets = set(list_sheet_names(workbook_path))

    for sheet_name in args.sheets:
        if sheet_name not in available_sheets:
            print(f"Skipping missing sheet: {sheet_name}")
            continue
        rows = read_sheet_rows(workbook_path, sheet_name)
        output_path = output_dir / f"{sheet_name}_current.csv"
        write_csv(output_path, rows)
        print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
