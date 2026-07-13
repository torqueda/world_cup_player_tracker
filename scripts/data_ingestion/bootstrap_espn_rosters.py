#!/usr/bin/env python3

"""
Bootstrap 2026 World Cup squad data from ESPN into raw_roster_import.csv.

This script is intentionally conservative:
- It imports raw roster text into the raw_roster_import schema.
- It does not try to create cleaned player IDs, club IDs, or Wikidata matches.
- It preserves the source wording for player names, clubs, positions, teams, and announcement notes.
- It should be treated as a bootstrap import, not the final authoritative dataset.

Output columns:
raw_roster_id
import_batch_id
source_name
source_url
source_checked_at
team
group
position_group_raw
player_name_raw
club_name_raw
shirt_number_raw
manager_raw
squad_announcement_date_raw
notes_raw
source_row_hash
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup


DEFAULT_ESPN_URL = (
    "https://www.espn.com/soccer/story/_/id/48757621/"
    "2026-world-cup-squad-lists-players-announced-all-48-teams"
)

OUTPUT_COLUMNS = [
    "raw_roster_id",
    "import_batch_id",
    "source_name",
    "source_url",
    "source_checked_at",
    "team",
    "group",
    "position_group_raw",
    "player_name_raw",
    "club_name_raw",
    "shirt_number_raw",
    "manager_raw",
    "squad_announcement_date_raw",
    "notes_raw",
    "source_row_hash",
]

POSITION_HEADINGS = [
    "Goalkeepers",
    "Defenders",
    "Midfielders",
    "Forwards",
]


@dataclass
class TeamBlock:
    group: str
    team: str
    texts: list[str] = field(default_factory=list)


def utc_now_string() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def make_import_batch_id(source_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{source_name.lower()}_{stamp}"


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_hash(*parts: str) -> str:
    joined = "||".join(clean_text(part).lower() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 compatible; WorldCupRosterResearchBot/0.1; "
            "+personal research project"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def looks_like_group_heading(text: str) -> bool:
    return bool(re.fullmatch(r"GROUP [A-L]", text.upper()))


def normalize_group_heading(text: str) -> str:
    match = re.search(r"GROUP\s+([A-L])", text.upper())
    if not match:
        return ""
    return f"Group {match.group(1)}"


def looks_like_team_heading(tag_name: str, text: str, current_group: str | None) -> bool:
    if not current_group:
        return False

    if tag_name not in {"h2", "h3"}:
        return False

    if looks_like_group_heading(text):
        return False

    reject_exact = {
        "2026 World Cup: Squad lists for all 48 teams",
        "Open Extended Reactions",
        "JUMP TO",
    }

    if text in reject_exact:
        return False

    if len(text) > 60:
        return False

    if ":" in text:
        return False

    return True


def extract_team_blocks(html: str) -> list[TeamBlock]:
    soup = BeautifulSoup(html, "html.parser")

    blocks: list[TeamBlock] = []
    current_group: str | None = None
    current_block: TeamBlock | None = None
    started = False

    for tag in soup.find_all(["h2", "h3", "p"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        if looks_like_group_heading(text):
            started = True
            current_group = normalize_group_heading(text)
            current_block = None
            continue

        if not started:
            continue

        if looks_like_team_heading(tag.name, text, current_group):
            current_block = TeamBlock(group=current_group or "", team=text)
            blocks.append(current_block)
            continue

        if current_block is not None:
            current_block.texts.append(text)

    return blocks


def extract_announcement_text(texts: Iterable[str]) -> str:
    for text in texts:
        lower = text.lower()
        if "announced" in lower and len(text) <= 160:
            return text.rstrip(".")
    return ""


def extract_manager(texts: Iterable[str]) -> str:
    for text in texts:
        match = re.match(r"Manager:\s*(.+)$", text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def parse_position_line(text: str) -> tuple[str, str] | None:
    for heading in POSITION_HEADINGS:
        match = re.match(rf"^{heading}\s*:\s*(.*)$", text)
        if match:
            return heading, clean_text(match.group(1))
    return None


def parse_player_club_entries(payload: str) -> list[tuple[str, str]]:
    """
    Parse strings like:
    Carlos Acevedo (Santos Laguna), Guillermo Ochoa (AEL Limassol)

    Returns:
    [("Carlos Acevedo", "Santos Laguna"), ("Guillermo Ochoa", "AEL Limassol")]
    """

    entries: list[tuple[str, str]] = []

    # Split only after a closing parenthesis followed by optional spaces then a comma.
    parts = re.split(r"\)\s*,\s*", payload)

    for part in parts:
        part = clean_text(part)
        if not part:
            continue

        part = re.sub(r"[.,;:]+$", "", part)
        if not part.endswith(")"):
            part = f"{part})"

        match = re.match(r"(?P<name>.+?)\s*\((?P<club>[^()]*)\)\s*[.,;:]*$", part)
        if not match:
            # Preserve failures as player name with blank club.
            entries.append((part.rstrip(",."), ""))
            continue

        player = clean_text(match.group("name").strip(" ,"))
        club = clean_text(match.group("club").strip(" ,"))
        entries.append((player, club))

    return entries


def build_rows(blocks: list[TeamBlock], source_url: str, source_checked_at: str) -> list[dict[str, str]]:
    import_batch_id = make_import_batch_id("espn")
    rows: list[dict[str, str]] = []
    row_number = 1

    for block in blocks:
        announcement = extract_announcement_text(block.texts)
        manager = extract_manager(block.texts)

        for text in block.texts:
            parsed = parse_position_line(text)
            if parsed is None:
                continue

            position_group, payload = parsed
            player_entries = parse_player_club_entries(payload)

            for player_name, club_name in player_entries:
                source_row_hash = make_hash(
                    block.team,
                    block.group,
                    position_group,
                    player_name,
                    club_name,
                    source_url,
                )

                raw_roster_id = f"raw_{import_batch_id}_{row_number:04d}"

                rows.append(
                    {
                        "raw_roster_id": raw_roster_id,
                        "import_batch_id": import_batch_id,
                        "source_name": "ESPN",
                        "source_url": source_url,
                        "source_checked_at": source_checked_at,
                        "team": block.team,
                        "group": block.group,
                        "position_group_raw": position_group,
                        "player_name_raw": player_name,
                        "club_name_raw": club_name,
                        "shirt_number_raw": "",
                        "manager_raw": manager,
                        "squad_announcement_date_raw": announcement,
                        "notes_raw": "",
                        "source_row_hash": source_row_hash,
                    }
                )

                row_number += 1

    return rows


def write_csv(rows: list[dict[str, str]], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str]]) -> None:
    team_counts: dict[str, int] = {}
    missing_club_count = 0

    for row in rows:
        team_counts[row["team"]] = team_counts.get(row["team"], 0) + 1
        if not row["club_name_raw"]:
            missing_club_count += 1

    print(f"Imported rows: {len(rows)}")
    print(f"Teams found: {len(team_counts)}")
    print(f"Rows with missing club: {missing_club_count}")
    print()

    for team, count in sorted(team_counts.items()):
        marker = "OK" if count == 26 else "CHECK"
        print(f"{marker:5} {team}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_ESPN_URL, help="Roster page URL to scrape.")
    parser.add_argument("--out", default="raw_roster_import.csv", help="Output CSV path.")
    parser.add_argument("--save-html", default="", help="Optional path to save fetched HTML.")
    args = parser.parse_args()

    source_checked_at = utc_now_string()

    try:
        html = fetch_html(args.url)
    except requests.HTTPError as exc:
        print(f"HTTP error while fetching source: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Network error while fetching source: {exc}", file=sys.stderr)
        return 1

    if args.save_html:
        with open(args.save_html, "w", encoding="utf-8") as f:
            f.write(html)

    blocks = extract_team_blocks(html)
    rows = build_rows(blocks, args.url, source_checked_at)

    if not rows:
        print("No roster rows were parsed. The page structure may have changed.", file=sys.stderr)
        return 1

    write_csv(rows, args.out)
    print(f"Wrote: {args.out}")
    print()
    print_summary(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())