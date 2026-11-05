#!/usr/bin/env python3
"""
Reconcile the Wikipedia-scraped final 2026 World Cup squads against the
current master dataset (via data/processed/master_exports/).

Outputs (to data/processed/final_roster_reconciliation/):

- roster_match_report.csv: one row per matched player — player_id, wiki shirt
  number, caps, goals, captain flag, plus a DOB cross-check column.
- players_cut_from_final_squads.csv: players in our dataset whose team's final
  squad no longer includes them (candidates for squad_status=removed).
- new_players_needing_ingestion.csv: Wikipedia final-squad players we don't
  have (late replacements) with everything Wikipedia gives us.
- reconciliation_summary.json: counts per team and overall.

Matching is conservative: exact ascii-folded name match within the same team
first, then a fuzzy pass (difflib) within the team at >= 0.88 similarity. A
shared birth date can stand in for name similarity, but only when the names
also share a word or are at least 0.5 similar, because teammates can share a
birthday; those links are labelled fuzzy+dob. Anything below that lands in the
unmatched outputs for manual review rather than being auto-linked.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECON_DIR = REPO_ROOT / "data/processed/final_roster_reconciliation"
EXPORTS = REPO_ROOT / "data/processed/master_exports"

# Our team names -> Wikipedia section headings.
TEAM_ALIASES = {
    "Czechia": "Czech Republic",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Curacao": "Curaçao",
    "Türkiye": "Turkey",
    "Ivory Coast": "Ivory Coast",
    "Cape Verde": "Cape Verde",
    "United States": "United States",
    "South Korea": "South Korea",
}


FUZZY_THRESHOLD = 0.88
# A shared birth date counts as this much name similarity...
DOB_SCORE = 0.95
# ...but only alongside some name evidence: a shared word, or this similarity.
DOB_MIN_SIMILARITY = 0.5
# Words too common in names to count as evidence on their own.
NAME_PARTICLES = frozenset(
    {"al", "el", "de", "da", "do", "dos", "das", "di", "du", "van", "von", "der", "den", "le", "la", "bin", "ibn", "jr"}
)


def fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z ]+", " ", text).strip()


def name_words(folded: str) -> set[str]:
    return {word for word in folded.split() if len(word) >= 3 and word not in NAME_PARTICLES}


def has_name_evidence(a_folded: str, b_folded: str, similarity: float) -> bool:
    """Whether two folded names show some sign, beyond a shared birthday, of being one person."""
    return similarity >= DOB_MIN_SIMILARITY or bool(name_words(a_folded) & name_words(b_folded))


def link_team(ours: list[dict[str, str]], theirs: list[dict[str, str]]) -> list[tuple[int, int, str]]:
    """Link one team's rows in our data to its rows in Wikipedia's final squad.

    `ours` rows need "folded" and "date_of_birth"; `theirs` rows need
    "player_name" and "date_of_birth". Returns (our index, their index, method)
    for each link, where method is "exact", "fuzzy:<similarity>" or
    "fuzzy+dob:<similarity>" (the link rests on the shared birth date).
    """
    links: list[tuple[int, int, str]] = []
    used_ours: set[int] = set()
    used_theirs: set[int] = set()

    # Pass 1: exact folded-name match.
    ours_index: dict[str, list[int]] = {}
    for i, our in enumerate(ours):
        ours_index.setdefault(our["folded"], []).append(i)
    for j, their in enumerate(theirs):
        candidates = [i for i in ours_index.get(fold(their["player_name"]), []) if i not in used_ours]
        if candidates:
            used_ours.add(candidates[0])
            used_theirs.add(j)
            links.append((candidates[0], j, "exact"))

    # Pass 2: closest remaining name within the team.
    for j, their in enumerate(theirs):
        if j in used_theirs:
            continue
        their_folded = fold(their["player_name"])
        best_i, best_score, best_similarity = None, 0.0, 0.0
        for i, our in enumerate(ours):
            if i in used_ours:
                continue
            similarity = SequenceMatcher(None, their_folded, our["folded"]).ratio()
            score = similarity
            # A shared birth date is strong evidence for short or rearranged names.
            same_dob = bool(their.get("date_of_birth")) and their["date_of_birth"] == our["date_of_birth"]
            if same_dob and has_name_evidence(their_folded, our["folded"], similarity):
                score = max(score, DOB_SCORE)
            if score > best_score:
                best_i, best_score, best_similarity = i, score, similarity
        if best_i is not None and best_score >= FUZZY_THRESHOLD:
            used_ours.add(best_i)
            used_theirs.add(j)
            label = "fuzzy" if best_similarity >= FUZZY_THRESHOLD else "fuzzy+dob"
            links.append((best_i, j, f"{label}:{best_similarity:.2f}"))
    return links


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        print(f"Wrote 0 rows to {path}")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main() -> None:
    wiki = read_csv(RECON_DIR / "wikipedia_final_squads.csv")
    players = {row["player_id"]: row for row in read_csv(EXPORTS / "players_current.csv")}
    squad_entries = read_csv(EXPORTS / "squad_entries_current.csv")

    ours_by_team: dict[str, list[dict[str, str]]] = {}
    for entry in squad_entries:
        wiki_team = TEAM_ALIASES.get(entry["team"], entry["team"])
        player = players.get(entry["player_id"])
        if not player:
            continue
        ours_by_team.setdefault(wiki_team, []).append(
            {
                "player_id": entry["player_id"],
                "team": entry["team"],
                "wiki_team": wiki_team,
                "display_name": player.get("display_name", ""),
                "name_ascii": player.get("name_ascii", ""),
                "date_of_birth": (player.get("date_of_birth") or "")[:10],
                "folded": fold(player.get("name_ascii") or player.get("display_name") or ""),
            }
        )

    wiki_by_team: dict[str, list[dict[str, str]]] = {}
    for row in wiki:
        wiki_by_team.setdefault(row["team"], []).append(row)

    matches: list[dict[str, object]] = []
    cut: list[dict[str, object]] = []
    new_players: list[dict[str, object]] = []
    fuzzy_count = 0

    all_teams = sorted(set(ours_by_team) | set(wiki_by_team))
    for team in all_teams:
        ours = list(ours_by_team.get(team, []))
        theirs = list(wiki_by_team.get(team, []))
        links = link_team(ours, theirs)
        used_ours = {i for i, _, _ in links}
        used_theirs = {j for _, j, _ in links}
        for i, j, method in links:
            matches.append(build_match(ours[i], theirs[j], method))
        fuzzy_count += sum(1 for _, _, method in links if method != "exact")

        for i, our in enumerate(ours):
            if i not in used_ours:
                cut.append(
                    {
                        "player_id": our["player_id"],
                        "team": our["team"],
                        "display_name": our["display_name"],
                        "date_of_birth": our["date_of_birth"],
                        "action_hint": "mark squad_status=removed unless matched manually",
                    }
                )
        for j, their in enumerate(theirs):
            if j not in used_theirs:
                new_players.append(dict(their) | {"action_hint": "new player: needs ingestion mini-pipeline"})

    dob_mismatches = [m for m in matches if m["dob_check"] == "MISMATCH"]

    write_csv(RECON_DIR / "roster_match_report.csv", matches)
    write_csv(RECON_DIR / "players_cut_from_final_squads.csv", cut)
    write_csv(RECON_DIR / "new_players_needing_ingestion.csv", new_players)

    summary = {
        "our_squad_entries": len(squad_entries),
        "wikipedia_final_squad_rows": len(wiki),
        "matched": len(matches),
        "matched_fuzzy": fuzzy_count,
        "cut_candidates": len(cut),
        "new_players": len(new_players),
        "dob_mismatches": len(dob_mismatches),
        "teams": {
            team: {
                "ours": len(ours_by_team.get(team, [])),
                "wikipedia": len(wiki_by_team.get(team, [])),
            }
            for team in all_teams
        },
    }
    (RECON_DIR / "reconciliation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"\nMatched {len(matches)} ({fuzzy_count} fuzzy) | cut candidates {len(cut)} | "
        f"new players {len(new_players)} | DOB mismatches {len(dob_mismatches)}"
    )


def build_match(our: dict[str, str], their: dict[str, str], method: str) -> dict[str, object]:
    our_dob = our["date_of_birth"]
    their_dob = their.get("date_of_birth") or ""
    if not our_dob or not their_dob:
        dob_check = "MISSING"
    elif our_dob == their_dob:
        dob_check = "OK"
    else:
        dob_check = "MISMATCH"
    return {
        "player_id": our["player_id"],
        "team": our["team"],
        "display_name": our["display_name"],
        "wiki_player_name": their["player_name"],
        "match_method": method,
        "shirt_number": their.get("shirt_number"),
        "position": their.get("position"),
        "is_captain": their.get("is_captain"),
        "caps_pre_tournament": their.get("caps"),
        "goals_pre_tournament": their.get("goals"),
        "wiki_club": their.get("club"),
        "our_dob": our_dob,
        "wiki_dob": their_dob,
        "dob_check": dob_check,
    }


if __name__ == "__main__":
    main()
