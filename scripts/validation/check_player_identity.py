#!/usr/bin/env python3
"""
Check each active player's identity against sources the Wikidata match did
not come from.

The integrity checks show the data agrees with itself, and so does a complete
record of the wrong person. Five players were matched to a namesake and passed
every integrity check (see change_log, 2026-11-05). These checks compare each
player with a second source instead:

- birth_date: the birth date in our data against Wikipedia's final squad.
- position: a goalkeeper in Wikipedia's final squad matched to a Wikidata
  entity listed only in outfield positions, or the other way round. The
  entity's positions come from the matcher's cached facts.

validate_player_identity_against_wikidata.py compares a QID with live Wikidata,
which cannot catch a namesake whose own facts are consistent.

Every finding must be listed in data/quality/identity_review.csv, with the
same values, or tests/test_player_identity.py fails. A new disagreement
therefore gets looked at before it ships, and the file stays a current list
of what is still open.

Usage:
    python scripts/validation/check_player_identity.py           # list findings
    python scripts/validation/check_player_identity.py --write   # also rewrite the review file
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "data_pipeline"))
from reconcile_final_rosters import TEAM_ALIASES, fold, link_team  # noqa: E402

EXPORTS = REPO_ROOT / "data/processed/app_exports"
WIKIPEDIA_SQUADS = REPO_ROOT / "data/processed/final_roster_reconciliation/wikipedia_final_squads.csv"
WIKIDATA_FACTS = REPO_ROOT / "data/processed/player_wikidata_matching/cache/wikidata_facts_cache.json"
REVIEW_FILE = REPO_ROOT / "data/quality/identity_review.csv"

REVIEW_FIELDS = ["check", "player_id", "team", "display_name", "ours", "second_source", "detail", "status", "note"]
# open: nobody has looked yet. same_person: the match is right and the sources
# disagree on this value. wrong_person: the match is wrong and needs a fix.
STATUSES = ("open", "same_person", "wrong_person")


@dataclass(frozen=True)
class Finding:
    check: str
    player_id: str
    team: str
    display_name: str
    ours: str
    second_source: str
    detail: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.check, self.player_id, self.ours, self.second_source)


def read_json(name: str):
    return json.loads((EXPORTS / name).read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def linked_players() -> list[tuple[dict, dict]]:
    """Pair each active player with their row in Wikipedia's final squad."""
    players = {row["player_id"]: row for row in read_json("players.json")}
    ours_by_team: dict[str, list[dict]] = {}
    for entry in read_json("squad_entries.json"):
        player = players.get(entry["player_id"])
        if entry.get("squad_status") != "active" or not player:
            continue
        team = TEAM_ALIASES.get(entry["team"], entry["team"])
        ours_by_team.setdefault(team, []).append(
            player
            | {
                "team": entry["team"],
                "folded": fold(player.get("name_ascii") or player.get("display_name") or ""),
                "date_of_birth": (player.get("date_of_birth") or "")[:10],
            }
        )
    theirs_by_team: dict[str, list[dict]] = {}
    for row in read_csv(WIKIPEDIA_SQUADS):
        theirs_by_team.setdefault(row["team"], []).append(row)

    pairs = []
    for team, ours in ours_by_team.items():
        theirs = theirs_by_team.get(team, [])
        pairs.extend((ours[i], theirs[j]) for i, j, _ in link_team(ours, theirs))
    return pairs


def describe_gap(ours: str, theirs: str) -> str:
    a, b = date.fromisoformat(ours), date.fromisoformat(theirs)
    days = abs((a - b).days)
    if days <= 3:
        return f"{days} day{'s' if days > 1 else ''} apart"
    if a.year == b.year and a.month == b.day and a.day == b.month:
        return "day and month swapped"
    if days in (365, 366) and (a.month, a.day) == (b.month, b.day):
        return "exactly one year apart"
    if (a.month, a.day) == (1, 1) or (b.month, b.day) == (1, 1):
        return f"{days} days apart; one source gives 1 January, often a placeholder"
    return f"{days} days apart"


def birth_date_findings(pairs: list[tuple[dict, dict]]) -> list[Finding]:
    findings = []
    for ours, theirs in pairs:
        our_dob, their_dob = ours["date_of_birth"], theirs.get("date_of_birth") or ""
        if our_dob and their_dob and our_dob != their_dob:
            findings.append(Finding(
                "birth_date", ours["player_id"], ours["team"], ours["display_name"],
                our_dob, their_dob, describe_gap(our_dob, their_dob),
            ))
    return findings


def position_findings(pairs: list[tuple[dict, dict]], facts: dict[str, dict]) -> list[Finding]:
    findings = []
    for ours, theirs in pairs:
        entity = facts.get(ours.get("wikidata_id") or "")
        positions = [p.strip().lower() for p in (entity or {}).get("positions", "").split("|") if p.strip()]
        if not positions:
            continue
        entity_keeper = any("goalkeeper" in p for p in positions)
        squad_keeper = theirs.get("position") == "GK"
        if entity_keeper != squad_keeper:
            findings.append(Finding(
                "position", ours["player_id"], ours["team"], ours["display_name"],
                f"{ours['wikidata_id']}: {'|'.join(positions)}", theirs.get("position") or "",
                "goalkeeper matched to an outfield player" if squad_keeper else "outfield player matched to a goalkeeper",
            ))
    return findings


def find_all() -> list[Finding]:
    pairs = linked_players()
    facts = json.loads(WIKIDATA_FACTS.read_text(encoding="utf-8"))
    findings = birth_date_findings(pairs) + position_findings(pairs, facts)
    return sorted(findings, key=lambda f: (f.check, f.team, f.display_name))


def read_review_file() -> dict[tuple[str, str, str, str], dict[str, str]]:
    if not REVIEW_FILE.exists():
        return {}
    rows = read_csv(REVIEW_FILE)
    return {(row["check"], row["player_id"], row["ours"], row["second_source"]): row for row in rows}


def write_review_file(findings: list[Finding]) -> None:
    reviewed = read_review_file()
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEW_FIELDS, lineterminator="\n")
        writer.writeheader()
        for finding in findings:
            previous = reviewed.get(finding.key, {})
            writer.writerow({
                "check": finding.check,
                "player_id": finding.player_id,
                "team": finding.team,
                "display_name": finding.display_name,
                "ours": finding.ours,
                "second_source": finding.second_source,
                "detail": finding.detail,
                "status": previous.get("status") or "open",
                "note": previous.get("note", ""),
            })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help=f"rewrite {REVIEW_FILE.relative_to(REPO_ROOT)}")
    args = parser.parse_args()

    findings = find_all()
    reviewed = read_review_file()
    for finding in findings:
        status = reviewed.get(finding.key, {}).get("status", "NOT LISTED")
        print(f"{finding.check:10} {status:12} {finding.team:14} {finding.display_name:26} "
              f"ours {finding.ours:24} second source {finding.second_source:12} {finding.detail}")
    unlisted = sum(1 for finding in findings if finding.key not in reviewed)
    stale = len(set(reviewed) - {finding.key for finding in findings})
    print(f"\n{len(findings)} findings, {unlisted} not in the review file, {stale} review rows no longer found")
    if args.write:
        write_review_file(findings)
        print(f"Wrote {REVIEW_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
