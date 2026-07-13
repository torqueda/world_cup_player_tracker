#!/usr/bin/env python3
"""
Scrape the final 2026 FIFA World Cup squads from Wikipedia.

Fetches https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads (archiving the
raw HTML to data/raw/ for provenance), then parses every team section into:

- wikipedia_final_squads.csv: one row per player on a final 26-man list
  (team, shirt number, position, name, date of birth, caps, goals, club,
  club country, captain flag)
- wikipedia_coaches.csv: one row per team coach (with nationality when the
  coach's flag differs from the team)
- wikipedia_squad_notes.csv: the per-team prose paragraphs (squad announcement
  dates, injury replacements, withdrawals) kept verbatim for manual review,
  since replacement wording is irregular and safer to review than auto-parse.

Wikipedia article text is CC BY-SA; the data itself is uncopyrightable fact.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]

SQUADS_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
USER_AGENT = (
    "WorldCupPlayerTracker/0.1 (non-commercial research project; "
    "contact: torqueda@andrew.cmu.edu)"
)

POSITION_CODES = {"GK", "DF", "MF", "FW"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-output",
        default=str(REPO_ROOT / "data/raw/wikipedia_2026_squads_snapshot.html"),
        help="Where to archive the fetched HTML.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data/processed/final_roster_reconciliation"),
        help="Directory for parsed CSV outputs.",
    )
    parser.add_argument(
        "--from-snapshot",
        action="store_true",
        help="Parse the existing snapshot instead of fetching the live page.",
    )
    return parser.parse_args()


def fetch_html(snapshot_path: Path, from_snapshot: bool) -> str:
    if from_snapshot:
        return snapshot_path.read_text(encoding="utf-8")
    response = requests.get(SQUADS_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(response.text, encoding="utf-8")
    return response.text


def clean_text(value: str) -> str:
    text = re.sub(r"\[[^\]]*\]", "", value)  # strip footnote markers like [4]
    return re.sub(r"\s+", " ", text).replace(" ", " ").strip()


def parse_dob(cell_text: str) -> str | None:
    match = re.search(r"\(\s*(\d{4}-\d{2}-\d{2})\s*\)", cell_text)
    if match:
        return match.group(1)
    for pattern, fmt in ((r"(\d{1,2} \w+ \d{4})", "%d %B %Y"), (r"(\w+ \d{1,2}, \d{4})", "%B %d, %Y")):
        match = re.search(pattern, cell_text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt).date().isoformat()
            except ValueError:
                continue
    return None


def parse_int(cell_text: str) -> int | None:
    text = clean_text(cell_text)
    return int(text) if text.lstrip("-").isdigit() else None


def club_country(cell) -> str | None:
    flag = cell.find("img")
    if flag and flag.get("alt"):
        return clean_text(flag["alt"]) or None
    return None


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(Path(args.snapshot_output), args.from_snapshot)
    soup = BeautifulSoup(html, "html.parser")

    players: list[dict[str, object]] = []
    coaches: list[dict[str, object]] = []
    notes: list[dict[str, object]] = []

    current_group = None
    current_team = None

    # The page can contain more than one mw-parser-output div (the first may be
    # an empty style holder); use the one that actually contains the tables.
    content = max(
        soup.find_all("div", class_="mw-parser-output"),
        key=lambda div: len(div.find_all("table")),
    )
    for element in content.find_all(["h2", "h3", "p", "table"]):
        if element.name == "h2":
            heading = clean_text(element.get_text())
            current_group = heading if heading.startswith("Group") else None
            if not current_group:
                current_team = None
        elif element.name == "h3":
            if current_group:
                current_team = clean_text(element.get_text())
        elif element.name == "p" and current_team:
            text = clean_text(element.get_text())
            if not text:
                continue
            if text.startswith("Coach:"):
                coach_name = clean_text(text.removeprefix("Coach:"))
                flag = element.find("img")
                coaches.append(
                    {
                        "group": current_group,
                        "team": current_team,
                        "coach_name": coach_name,
                        "coach_nationality": clean_text(flag["alt"]) if flag and flag.get("alt") else None,
                    }
                )
            else:
                notes.append({"group": current_group, "team": current_team, "note": text})
        elif element.name == "table" and current_team:
            classes = element.get("class") or []
            if "sortable" not in classes and "nat-fs-player" not in " ".join(classes):
                continue
            for row in element.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) < 7:
                    continue
                texts = [clean_text(cell.get_text(" ")) for cell in cells]
                # The position cell carries a hidden numeric sort key, e.g. "1 GK".
                pos_match = re.search(r"\b(GK|DF|MF|FW)\b", texts[1])
                if not pos_match:
                    continue  # header or malformed row
                name = texts[2]
                players.append(
                    {
                        "group": current_group,
                        "team": current_team,
                        "shirt_number": parse_int(texts[0]),
                        "position": pos_match.group(1),
                        "player_name": re.sub(r"\s*\(\s*captain\s*\)\s*", "", name, flags=re.I),
                        "is_captain": bool(re.search(r"\(\s*captain\s*\)", name, re.I)),
                        "date_of_birth": parse_dob(texts[3]),
                        "caps": parse_int(texts[4]),
                        "goals": parse_int(texts[5]),
                        "club": texts[6],
                        "club_country": club_country(cells[6]),
                    }
                )

    def write(name: str, rows: list[dict[str, object]]) -> None:
        path = output_dir / name
        if not rows:
            print(f"WARNING: no rows for {name}")
            return
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} rows to {path}")

    write("wikipedia_final_squads.csv", players)
    write("wikipedia_coaches.csv", coaches)
    write("wikipedia_squad_notes.csv", notes)

    teams = sorted({str(p["team"]) for p in players})
    print(f"\nTeams parsed: {len(teams)}")
    counts = {team: sum(1 for p in players if p["team"] == team) for team in teams}
    odd = {team: n for team, n in counts.items() if n != 26}
    if odd:
        print(f"Teams without exactly 26 players: {odd}")
    print(f"Fetched at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
