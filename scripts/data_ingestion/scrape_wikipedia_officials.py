#!/usr/bin/env python3
"""
Scrape the 2026 FIFA World Cup match officials from Wikipedia.

Archives the raw HTML to data/raw/ and writes
data/processed/final_roster_reconciliation/wikipedia_match_officials.csv with
one row per official: role section, confederation (when the table provides
it), name, and country.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]
URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_officials"
USER_AGENT = (
    "WorldCupPlayerTracker/0.1 (non-commercial research project; "
    "contact: torqueda@andrew.cmu.edu)"
)
SNAPSHOT = REPO_ROOT / "data/raw/wikipedia_2026_officials_snapshot.html"
OUTPUT = REPO_ROOT / "data/processed/final_roster_reconciliation/wikipedia_match_officials.csv"


def clean(value: str) -> str:
    text = re.sub(r"\[[^\]]*\]", "", value)
    return re.sub(r"\s+", " ", text).replace(" ", " ").strip()


def expand_table_grid(table) -> list[list[str]]:
    """Expand a table into a rectangular grid, honoring rowspan/colspan."""
    grid: list[list[str | None]] = []
    for row_index, row in enumerate(table.find_all("tr")):
        while len(grid) <= row_index:
            grid.append([])
        col = 0
        for cell in row.find_all(["th", "td"]):
            while col < len(grid[row_index]) and grid[row_index][col] is not None:
                col += 1
            text = clean(cell.get_text(" "))
            rowspan = int(cell.get("rowspan") or 1)
            colspan = int(cell.get("colspan") or 1)
            for dr in range(rowspan):
                target_row = row_index + dr
                while len(grid) <= target_row:
                    grid.append([])
                while len(grid[target_row]) < col + colspan:
                    grid[target_row].append(None)
                for dc in range(colspan):
                    grid[target_row][col + dc] = text
            col += colspan
    return [[value or "" for value in row] for row in grid if row]


def main() -> None:
    if SNAPSHOT.exists():
        html = SNAPSHOT.read_text(encoding="utf-8")
    else:
        response = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=60)
        response.raise_for_status()
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(response.text, encoding="utf-8")
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    content = max(
        soup.find_all("div", class_="mw-parser-output"),
        key=lambda div: len(div.find_all("table")),
    )

    rows_out: list[dict[str, str]] = []
    current_section = None

    for element in content.find_all(["h2", "h3", "table"]):
        if element.name in ("h2", "h3"):
            current_section = clean(element.get_text())
            continue
        classes = " ".join(element.get("class") or [])
        if "wikitable" not in classes:
            continue
        grid = expand_table_grid(element)
        if not grid:
            continue
        header_cells = grid[0]
        for values in grid[1:]:
            if not any(values):
                continue
            record = {"section": current_section or ""}
            for i, value in enumerate(values):
                key = header_cells[i] if i < len(header_cells) else f"col_{i}"
                record[key or f"col_{i}"] = value
            rows_out.append(record)

    fieldnames: list[str] = []
    for record in rows_out:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} official rows to {OUTPUT}")
    sections = {}
    for record in rows_out:
        sections[record["section"]] = sections.get(record["section"], 0) + 1
    for section, count in sections.items():
        print(f"  {section}: {count}")


if __name__ == "__main__":
    main()
