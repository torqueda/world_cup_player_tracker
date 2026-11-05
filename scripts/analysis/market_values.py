#!/usr/bin/env python3
"""
Link the players in the final squads to Transfermarkt and take each one's
market value on the eve of the tournament.

Source: the players and player_valuations tables of dcaribou's
transfermarkt-datasets (CC0), https://github.com/dcaribou/transfermarkt-datasets.
Its valuations stop on 2026-06-12, so every value here is from before the
tournament. The full tables are large and are not committed; this script reads
them from wherever they were downloaded and writes a small snapshot, which the
analysis scripts read instead.

Linking. Transfermarkt has no Wikidata or FIFA IDs in these tables, so each
player is linked on birth date, name, citizenship and club:

- dob_and_name: Transfermarkt's birth date equals one of the player's birth
  dates (FIFA's final squad list as published on Wikipedia, the tracker's, or
  that of the player's Wikidata record in the matcher's cache), and the names
  agree: a name similarity of at least 0.9, or at
  least 0.75 (or Transfermarkt's surname inside the tracker's name) with the
  same citizenship or club.
- dob_citizenship_and_club: same birth date, citizenship and club, with a
  weaker name match (0.5 or more), for players known by another name.
- name_citizenship_and_club: the birth dates differ, but the names match
  (0.94 or more), and so do the citizenship and the club. These are listed in
  the summary, since one of the two birth dates is wrong.

A link is kept only when it is the single best candidate and no other squad
player takes the same Transfermarkt player.

Each linked player's value is the last valuation dated before the tournament
started (2026-06-11). Players without a link or a valuation have no value.

Outputs:
- data/raw/transfermarkt_wc2026_snapshot.csv: one row per player in a final
  squad, with the link and the value.
- data/processed/analysis/market_values_2026.json: how many players were
  linked and by which rule, the value per team, and the players whose birth
  dates disagree.

Usage:
    python scripts/analysis/market_values.py PLAYERS_CSV_GZ PLAYER_VALUATIONS_CSV_GZ
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from analysis_data import MARKET_VALUES as SNAPSHOT
from analysis_data import REPO_ROOT, TOURNAMENT_START, VALUES_SET_SINCE, country_name, read_export, write_output

WIKIPEDIA_SQUADS = REPO_ROOT / "data/processed/final_roster_reconciliation/wikipedia_final_squads.csv"
# The matcher's cached Wikidata facts. The tracker takes FIFA's birth date where
# the two disagree, and Transfermarkt sometimes has Wikidata's.
WIKIDATA_FACTS = REPO_ROOT / "data/processed/player_wikidata_matching/cache/wikidata_facts_cache.json"
SNAPSHOT_FIELDS = [
    "player_id", "team", "display_name", "date_of_birth",
    "tm_player_id", "tm_name", "tm_date_of_birth", "tm_citizenship", "tm_club", "link_method",
    "market_value_eur", "valuation_date",
]
# Transfermarkt's spelling of the citizenship, where it differs from the team name.
CITIZENSHIP = {
    "Congo DR": {"DR Congo"},
    "Czechia": {"Czech Republic"},
    "Ivory Coast": {"Cote d'Ivoire"},
    "South Korea": {"Korea, South"},
    "Türkiye": {"Türkiye", "Turkey"},
}


def words(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z]+", ascii_text))


def name_similarity(ours: list[str], theirs: str) -> float:
    best = 0.0
    t = words(theirs)
    for name in ours:
        o = words(name)
        if not o or not t:
            continue
        shared = len(set(o.split()) & set(t.split())) / min(len(o.split()), len(t.split()))
        best = max(best, SequenceMatcher(None, o, t).ratio(), shared)
    return best


def surname_inside(ours: list[str], surname: str) -> bool:
    s = set(words(surname).split())
    return bool(s) and any(s <= set(words(name).split()) for name in ours)


def same_club(ours: str, theirs: str) -> bool:
    generic = {"fc", "cf", "sc", "ac", "club", "de", "fk", "sk", "cd", "ca", "afc", "football", "futbol", "the"}
    a = set(words(ours).split()) - generic
    b = set(words(theirs).split()) - generic
    return bool(a & b) or SequenceMatcher(None, words(ours), words(theirs)).ratio() >= 0.75


def read_gzip_csv(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def squad_players() -> list[dict]:
    """Each player in a final squad, with every birth date the sources give."""
    players = {p["player_id"]: p for p in read_export("players")}
    clubs = {c["club_id"]: c for c in read_export("clubs")}
    callups = {c["player_id"]: c for c in read_export("player_club_at_callup")}
    with WIKIPEDIA_SQUADS.open(encoding="utf-8-sig", newline="") as handle:
        fifa_dob = {(r["team"], str(r["shirt_number"])): r["date_of_birth"][:10] for r in csv.DictReader(handle)}
    wikidata_dob = {
        qid: (facts.get("date_of_birth") or "")[:10]
        for qid, facts in json.loads(WIKIDATA_FACTS.read_text(encoding="utf-8")).items()
    }
    rows = []
    for entry in read_export("squad_entries"):
        if entry["squad_status"] != "active":
            continue
        player = players[entry["player_id"]]
        dob = (player["date_of_birth"] or "")[:10]
        rows.append({
            "player_id": entry["player_id"],
            "team": entry["team"],
            "display_name": player["display_name"],
            "names": [player["display_name"], player["name_ascii"] or "", entry["display_name_at_source"] or ""],
            "dates": {d for d in (
                dob,
                fifa_dob.get((country_name(entry["team"]), str(entry["shirt_number"]))),
                wikidata_dob.get(player["wikidata_id"] or ""),
            ) if d},
            "date_of_birth": dob,
            "club": clubs[callups[entry["player_id"]]["club_id"]]["club_name"],
            "citizenships": CITIZENSHIP.get(entry["team"], {entry["team"]}),
        })
    return rows


def link(player: dict, by_dob: dict[str, list[dict]], by_citizenship: dict[str, list[dict]]) -> tuple[dict, str] | None:
    candidates = []
    for date in player["dates"]:
        for c in by_dob.get(date, []):
            name = name_similarity(player["names"], c["name"])
            citizen = c["country_of_citizenship"] in player["citizenships"]
            club = same_club(player["club"], c["current_club_name"])
            surname = surname_inside(player["names"], c["last_name"])
            if name >= 0.9 or ((name >= 0.75 or surname) and (citizen or club)):
                candidates.append((2, name, c, "dob_and_name"))
            elif name >= 0.5 and citizen and club:
                candidates.append((1, name, c, "dob_citizenship_and_club"))
    if not candidates:
        for citizenship in player["citizenships"]:
            for c in by_citizenship.get(citizenship, []):
                name = name_similarity(player["names"], c["name"])
                if name >= 0.94 and same_club(player["club"], c["current_club_name"]):
                    candidates.append((0, name, c, "name_citizenship_and_club"))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = candidates[0]
    rivals = [x for x in candidates[1:] if x[2]["player_id"] != best[2]["player_id"]]
    if rivals and (rivals[0][0], rivals[0][1]) == (best[0], best[1]):
        return None  # two equally good candidates: leave unlinked
    return best[2], best[3]


def last_value_before_start(valuations: list[dict], wanted: set[str]) -> dict[str, tuple[int, str]]:
    latest: dict[str, tuple[int, str]] = {}
    for v in valuations:
        pid, day = v["player_id"], v["date"][:10]
        if pid in wanted and day < TOURNAMENT_START and (pid not in latest or day > latest[pid][1]):
            latest[pid] = (int(float(v["market_value_in_eur"])), day)
    return latest


def build(players_path: Path, valuations_path: Path) -> tuple[list[dict], dict]:
    tm_players = read_gzip_csv(players_path)
    by_dob: dict[str, list[dict]] = defaultdict(list)
    by_citizenship: dict[str, list[dict]] = defaultdict(list)
    for c in tm_players:
        by_dob[c["date_of_birth"][:10]].append(c)
        by_citizenship[c["country_of_citizenship"]].append(c)

    squad = squad_players()
    links = {p["player_id"]: link(p, by_dob, by_citizenship) for p in squad}
    taken = Counter(found[0]["player_id"] for found in links.values() if found)
    for pid, found in links.items():
        if found and taken[found[0]["player_id"]] > 1:
            links[pid] = None  # two squad players on one Transfermarkt player: trust neither

    wanted = {found[0]["player_id"] for found in links.values() if found}
    values = last_value_before_start(read_gzip_csv(valuations_path), wanted)

    rows = []
    for p in squad:
        found = links[p["player_id"]]
        c, method = found if found else ({}, "none")
        value, day = values.get(c.get("player_id"), (None, None))
        rows.append({
            "player_id": p["player_id"],
            "team": p["team"],
            "display_name": p["display_name"],
            "date_of_birth": p["date_of_birth"],
            "tm_player_id": c.get("player_id", ""),
            "tm_name": c.get("name", ""),
            "tm_date_of_birth": c.get("date_of_birth", "")[:10],
            "tm_citizenship": c.get("country_of_citizenship", ""),
            "tm_club": c.get("current_club_name", ""),
            "link_method": method,
            "market_value_eur": value if value is not None else "",
            "valuation_date": day or "",
        })
    return rows, summarize(rows, squad)


def summarize(rows: list[dict], squad: list[dict]) -> dict:
    dates = {p["player_id"]: p["dates"] for p in squad}
    valued = [r for r in rows if r["market_value_eur"] != ""]
    by_team: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_team[r["team"]].append(r)
    teams = []
    for team, squad_rows in sorted(by_team.items()):
        known = [int(r["market_value_eur"]) for r in squad_rows if r["market_value_eur"] != ""]
        teams.append({
            "team": team,
            "players": len(squad_rows),
            "players_valued": len(known),
            "squad_value_eur": int(sum(known)),
            "median_player_value_eur": int(np.median(known)) if known else None,
        })
    ages = sorted(r["valuation_date"] for r in valued)
    return {
        "about": {
            "what": "Transfermarkt market values for the players in the final squads, from the last valuation "
                    "before the tournament started on 2026-06-11.",
            "source": "dcaribou/transfermarkt-datasets (CC0), players and player_valuations tables; valuations "
                      "end on 2026-06-12.",
            "linking": "On birth date, name, citizenship and club; see scripts/analysis/market_values.py for the "
                       "rules. A link is kept only when it is the single best candidate.",
            "players": len(rows),
            "linked": sum(r["link_method"] != "none" for r in rows),
            "linked_by": dict(Counter(r["link_method"] for r in rows)),
            "valued": len(valued),
            "valuation_dates": {"earliest": ages[0], "median": ages[len(ages) // 2], "latest": ages[-1]} if ages else None,
            "valued_in_the_12_months_before": sum(r["valuation_date"] >= VALUES_SET_SINCE for r in valued),
        },
        "teams": teams,
        "birth_dates_that_disagree": [
            {"player_id": r["player_id"], "team": r["team"], "display_name": r["display_name"],
             "tracker_and_fifa": sorted(dates[r["player_id"]]), "transfermarkt": r["tm_date_of_birth"],
             "tm_name": r["tm_name"]}
            for r in rows
            if r["link_method"] != "none" and r["tm_date_of_birth"] not in dates[r["player_id"]]
        ],
        "not_linked": [{"team": r["team"], "display_name": r["display_name"]} for r in rows if r["link_method"] == "none"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("players", type=Path, help="transfermarkt-datasets players.csv.gz")
    parser.add_argument("valuations", type=Path, help="transfermarkt-datasets player_valuations.csv.gz")
    args = parser.parse_args()
    rows, summary = build(args.players, args.valuations)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {SNAPSHOT.relative_to(REPO_ROOT)}")
    print(f"Wrote {write_output('market_values_2026', summary).relative_to(REPO_ROOT)}")
    a = summary["about"]
    print(f"Linked {a['linked']} of {a['players']} {a['linked_by']}; valued {a['valued']}; "
          f"dates {a['valuation_dates']}; in the 12 months before: {a['valued_in_the_12_months_before']}")
    print(f"Birth dates that disagree: {len(summary['birth_dates_that_disagree'])}; "
          f"not linked: {len(summary['not_linked'])}")


if __name__ == "__main__":
    main()
