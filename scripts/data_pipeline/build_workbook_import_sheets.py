#!/usr/bin/env python3
"""
Merge all 2026 tournament collection outputs into import-ready sheets for the
master workbook.

Inputs (already collected):
- data/processed/final_roster_reconciliation/ (Wikipedia squads, coaches,
  officials, roster reconciliation outputs)
- data/raw/fifa_player_stats_golden_boot_tab.csv (goals/assists/minutes)
- data/raw/fifa_player_stats_discipline_tab.csv (cards)
- data/raw/fifa_team_stats_attacking_tab.csv (team goals/xG/possession)
- data/raw/fifa_scores_fixtures_snapshot.txt (all match results)
- data/processed/master_exports/ (current workbook snapshots)

Outputs (data/processed/workbook_import/): one CSV per workbook sheet to
create or update. Nothing touches the workbook itself — these are for manual
import into Google Sheets, after which the normal refresh pipeline runs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECON = REPO_ROOT / "data/processed/final_roster_reconciliation"
RAW = REPO_ROOT / "data/raw"
EXPORTS = REPO_ROOT / "data/processed/master_exports"
OUT = REPO_ROOT / "data/processed/workbook_import"

TODAY = date.today().isoformat()
TOURNAMENT = "wc2026"

# Wikipedia team headings -> our team names.
WIKI_TO_OURS = {
    "Czech Republic": "Czechia",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "DR Congo": "Congo DR",
    "Curaçao": "Curacao",
    "Turkey": "Türkiye",
}
# FIFA fixture team names -> our team names.
FIFA_TO_OURS = {
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Cabo Verde": "Cape Verde",
    "Côte d'Ivoire": "Ivory Coast",
    "USA": "United States",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Curaçao": "Curacao",
}
POSITION_GROUPS = {"GK": "goalkeeper", "DF": "defender", "MF": "midfielder", "FW": "forward"}

NEW_SOURCES = [
    {
        "source_id": "wiki_squads_2026",
        "source_name": "Wikipedia: 2026 FIFA World Cup squads",
        "url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
        "retrieved_at": TODAY,
        "notes": "Final 26-man rosters, shirt numbers, coaches, replacement notes. Snapshot: data/raw/wikipedia_2026_squads_snapshot.html",
    },
    {
        "source_id": "wiki_officials_2026",
        "source_name": "Wikipedia: 2026 FIFA World Cup officials",
        "url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_officials",
        "retrieved_at": TODAY,
        "notes": "Referees, assistants, VARs with match assignments. Snapshot: data/raw/wikipedia_2026_officials_snapshot.html",
    },
    {
        "source_id": "fifa_player_stats_2026",
        "source_name": "FIFA.com player statistics (through quarterfinals)",
        "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/player-statistics",
        "retrieved_at": TODAY,
        "notes": "Goals/assists/minutes for all registered players; cards from Discipline tab. Collected from rendered pages.",
    },
    {
        "source_id": "fifa_team_stats_2026",
        "source_name": "FIFA.com team statistics (through quarterfinals)",
        "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/team-statistics",
        "retrieved_at": TODAY,
        "notes": "Team goals, assists, xG, possession. Collected from rendered pages.",
    },
    {
        "source_id": "fifa_fixtures_2026",
        "source_name": "FIFA.com scores & fixtures",
        "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures",
        "retrieved_at": TODAY,
        "notes": "All match results through the quarterfinals plus remaining schedule. Snapshot: data/raw/fifa_scores_fixtures_snapshot.txt",
    },
]


NON_DECOMPOSABLE = str.maketrans(
    {"ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}
)


def fold(value: str) -> str:
    text = (value or "").translate(NON_DECOMPOSABLE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z ]+", " ", text.replace("-", " ")).strip()


def token_key(value: str) -> str:
    return " ".join(sorted(fold(value).split()))


def concat_key(value: str) -> str:
    return fold(value).replace(" ", "")


def slugify(value: str) -> str:
    text = fold(value)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "blank"


def short_hash(*parts: str) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:8]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if not rows:
        path.write_text("", encoding="utf-8")
        print(f"Wrote 0 rows to {path}")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main() -> None:
    players = read_csv(EXPORTS / "players_current.csv")
    squad_entries = read_csv(EXPORTS / "squad_entries_current.csv")
    clubs = read_csv(EXPORTS / "clubs_current.csv")
    match_report = read_csv(RECON / "roster_match_report.csv")
    cut_players = read_csv(RECON / "players_cut_from_final_squads.csv")
    new_wiki_players = read_csv(RECON / "new_players_needing_ingestion.csv")
    coaches = read_csv(RECON / "wikipedia_coaches.csv")
    officials = read_csv(RECON / "wikipedia_match_officials.csv")
    fifa_stats = read_csv(RAW / "fifa_player_stats_golden_boot_tab.csv")
    fifa_cards = read_csv(RAW / "fifa_player_stats_discipline_tab.csv")
    fifa_team_stats = read_csv(RAW / "fifa_team_stats_attacking_tab.csv")

    team_code_by_name = {row["team"]: row["team_code"] for row in squad_entries}
    entry_by_player = {row["player_id"]: row for row in squad_entries}
    club_by_fold = {}
    for club in clubs:
        club_by_fold.setdefault(fold(club.get("club_name_ascii") or club["club_name"]), club["club_id"])
        club_by_fold.setdefault(fold(club["club_name"]), club["club_id"])

    # ---- 1. New players (late replacements) --------------------------------
    new_player_rows = []
    new_squad_rows = []
    new_callup_rows = []
    new_club_rows = []
    new_clubs_seen: dict[str, str] = {}
    new_player_id_by_wiki_name: dict[tuple[str, str], str] = {}

    for row in new_wiki_players:
        our_team = WIKI_TO_OURS.get(row["team"], row["team"])
        team_code = team_code_by_name.get(our_team, "")
        pid = f"p_{team_code.lower()}_{slugify(row['player_name'])}_{short_hash(our_team, row['player_name'], row.get('date_of_birth') or '')}"
        new_player_id_by_wiki_name[(team_code, token_key(row["player_name"]))] = pid

        club_name = row.get("club") or ""
        club_id = club_by_fold.get(fold(club_name))
        if not club_id:
            if fold(club_name) in new_clubs_seen:
                club_id = new_clubs_seen[fold(club_name)]
            else:
                club_id = f"c_{slugify(club_name)}_{short_hash(club_name)}"
                new_clubs_seen[fold(club_name)] = club_id
                new_club_rows.append(
                    {
                        "club_id": club_id,
                        "wikidata_id": "",
                        "club_name": club_name,
                        "club_name_ascii": fold(club_name).title(),
                        "league": "",
                        "country": "",
                        "city": "",
                        "stadium": "",
                        "club_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                        "manual_review_flag": "TRUE",
                        "notes": f"New club from final-roster replacement import {TODAY}; club association per Wikipedia flag: {row.get('club_country') or 'unknown'}. Needs league/country/city/geocoding.",
                    }
                )

        new_player_rows.append(
            {
                "player_id": pid,
                "wikidata_id": "",
                "display_name": row["player_name"],
                "name_ascii": fold(row["player_name"]).title(),
                "date_of_birth": row.get("date_of_birth") or "",
                "place_of_birth": "",
                "birth_country": "",
                "primary_position": POSITION_GROUPS.get(row.get("position") or "", ""),
                "bio_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                "data_confidence": "wikipedia_squads_import",
                "manual_review_flag": "TRUE",
                "notes": f"Late final-squad addition imported {TODAY}; needs Wikidata match, birthplace, and enrichment.",
            }
        )
        new_squad_rows.append(
            {
                "squad_entry_id": f"se_{TOURNAMENT}_{team_code.lower()}_{short_hash(pid)}",
                "tournament": "FIFA World Cup 2026",
                "team": our_team,
                "team_code": team_code,
                "player_id": pid,
                "display_name_at_source": row["player_name"],
                "position_group": POSITION_GROUPS.get(row.get("position") or "", ""),
                "shirt_number": row.get("shirt_number") or "",
                "squad_status": "active",
                "is_replacement": "TRUE",
                "replaced_player_id": "",
                "replacement_reason": "joined final squad after ESPN snapshot; see wikipedia_squad_notes.csv for team announcement details",
                "official_roster_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                "verified_at": TODAY,
            }
        )
        new_callup_rows.append(
            {
                "player_club_callup_id": f"pc_{TOURNAMENT}_{short_hash(pid, club_id)}",
                "player_id": pid,
                "club_id": club_id,
                "team": our_team,
                "club_name_at_source": club_name,
                "club_rule": "club at final-squad announcement (Wikipedia)",
                "is_on_loan": "unknown",
                "parent_club_id": "",
                "loan_club_id": "",
                "club_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                "confidence": "medium",
                "notes": "",
            }
        )

    # ---- 2. Squad-entry updates (matched + cut) ----------------------------
    squad_updates = []
    for m in match_report:
        entry = entry_by_player.get(m["player_id"])
        if not entry:
            continue
        squad_updates.append(
            {
                "squad_entry_id": entry["squad_entry_id"],
                "player_id": m["player_id"],
                "team": m["team"],
                "shirt_number": m.get("shirt_number") or "",
                "is_captain": m.get("is_captain") or "",
                "squad_status": "active",
                "verified_at": TODAY,
                "official_roster_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                "caps_pre_tournament": m.get("caps_pre_tournament") or "",
                "goals_pre_tournament": m.get("goals_pre_tournament") or "",
                "notes": "confirmed on FIFA final squad list via Wikipedia squads page",
            }
        )
    for c in cut_players:
        entry = entry_by_player.get(c["player_id"])
        if not entry:
            continue
        squad_updates.append(
            {
                "squad_entry_id": entry["squad_entry_id"],
                "player_id": c["player_id"],
                "team": c["team"],
                "shirt_number": "",
                "is_captain": "",
                "squad_status": "removed",
                "verified_at": TODAY,
                "official_roster_source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
                "caps_pre_tournament": "",
                "goals_pre_tournament": "",
                "notes": "not on the FIFA final squad list; kept for history. See wikipedia_squad_notes.csv.",
            }
        )

    # ---- 3. Player stats ---------------------------------------------------
    players_by_id = {p["player_id"]: p for p in players}
    roster_by_team: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for m in match_report:
        code = team_code_by_name.get(m["team"], "")
        name = players_by_id.get(m["player_id"], {}).get("name_ascii") or m["display_name"]
        roster_by_team[code].append((token_key(name), concat_key(name), m["player_id"]))
    for row in new_wiki_players:
        our_team = WIKI_TO_OURS.get(row["team"], row["team"])
        code = team_code_by_name.get(our_team, "")
        pid = new_player_id_by_wiki_name[(code, token_key(row["player_name"]))]
        roster_by_team[code].append((token_key(row["player_name"]), concat_key(row["player_name"]), pid))

    def match_player(team_code: str, name: str) -> str | None:
        tkey, ckey = token_key(name), concat_key(name)
        candidates = roster_by_team.get(team_code, [])
        for cand_tkey, cand_ckey, pid in candidates:
            if cand_tkey == tkey or cand_ckey == ckey:
                return pid
        best_pid, best_score = None, 0.0
        for cand_tkey, cand_ckey, pid in candidates:
            score = max(
                SequenceMatcher(None, tkey, cand_tkey).ratio(),
                SequenceMatcher(None, ckey, cand_ckey).ratio(),
            )
            if score > best_score:
                best_pid, best_score = pid, score
        return best_pid if best_score >= 0.80 else None

    cards_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in fifa_cards:
        cards_by_key[(row["team_code"], token_key(row["player_name"]))] = row

    stats_rows = []
    unmatched_stats = []
    for row in fifa_stats:
        pid = match_player(row["team_code"], row["player_name"])
        card = cards_by_key.get((row["team_code"], token_key(row["player_name"])), {})
        record = {
            "player_id": pid or "",
            "tournament": "FIFA World Cup 2026",
            "team_code": row["team_code"],
            "fifa_listed_name": row["player_name"],
            "goals": row["goals"],
            "assists": row["assists"],
            "minutes_played": row["minutes_played"],
            "yellow_cards": card.get("yellow_cards") or "0",
            "red_cards": card.get("red_cards") or "0",
            "indirect_red_cards": card.get("indirect_red_cards") or "0",
            "as_of_stage": "through quarterfinals",
            "source_id": "fifa_player_stats_2026",
            "retrieved_at": TODAY,
        }
        if pid:
            stats_rows.append(record)
        else:
            unmatched_stats.append(record)

    # ---- 4. Matches / team stats -------------------------------------------
    matches = []
    current_date = None
    date_line = re.compile(r"^\w+ \d{2} \w+ \d{4}$|^\w+ \d{1,2} \w+ \d{4}$")
    for line in (RAW / "fifa_scores_fixtures_snapshot.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if date_line.match(line):
            current_date = line
            continue
        parts = line.split("|")
        if len(parts) != 8:
            continue
        home, home_score, away_score, away, stage, group, stadium, city = parts

        def score_and_pens(text: str) -> tuple[str, str]:
            m = re.match(r"^(\d+)(?: \((\d+)\))?$", text)
            return (m.group(1), m.group(2) or "") if m else ("", "")

        hs, hp = score_and_pens(home_score)
        as_, ap = score_and_pens(away_score)
        matches.append(
            {
                "match_id": f"m_{TOURNAMENT}_{short_hash(current_date or '', home, away)}",
                "tournament": "FIFA World Cup 2026",
                "match_date": current_date,
                "stage": stage,
                "group": group,
                "home_team": FIFA_TO_OURS.get(home, home),
                "away_team": FIFA_TO_OURS.get(away, away),
                "home_score": hs,
                "away_score": as_,
                "home_pens": hp,
                "away_pens": ap,
                "stadium": stadium,
                "city": city,
                "status": "played" if hs != "" else "scheduled",
                "source_id": "fifa_fixtures_2026",
            }
        )

    tallies: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    stage_reached: dict[str, str] = {}
    stage_rank = {"First Stage": 1, "Round of 32": 2, "Round of 16": 3, "Quarter-final": 4, "Semi-final": 5}
    for m in matches:
        if m["status"] != "played":
            if m["stage"] == "Semi-final":
                for team in (m["home_team"], m["away_team"]):
                    stage_reached[team] = "Semi-finals (in progress)"
            continue
        home, away = m["home_team"], m["away_team"]
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        for team, gf, ga in ((home, hs, as_), (away, as_, hs)):
            tallies[team]["played"] += 1
            tallies[team]["gf"] += gf
            tallies[team]["ga"] += ga
        if hs > as_:
            tallies[home]["won"] += 1
            tallies[away]["lost"] += 1
        elif hs < as_:
            tallies[away]["won"] += 1
            tallies[home]["lost"] += 1
        else:
            tallies[home]["drawn"] += 1
            tallies[away]["drawn"] += 1
        # record the deepest stage each team has played in
        for team in (home, away):
            best = stage_reached.get(team)
            if best == "Semi-finals (in progress)":
                continue
            best_rank = {"Group stage": 1, "Round of 32": 2, "Round of 16": 3, "Quarter-finals": 4}.get(best or "", 0)
            label = {"First Stage": "Group stage", "Round of 32": "Round of 32", "Round of 16": "Round of 16", "Quarter-final": "Quarter-finals"}.get(m["stage"], m["stage"])
            if stage_rank.get(m["stage"], 0) >= best_rank:
                stage_reached[team] = label

    team_stats_rows = []
    for row in fifa_team_stats:
        our_team = FIFA_TO_OURS.get(row["team"], row["team"])
        t = tallies.get(our_team, {})
        team_stats_rows.append(
            {
                "team": our_team,
                "team_code": team_code_by_name.get(our_team, ""),
                "tournament": "FIFA World Cup 2026",
                "matches_played": t.get("played", 0),
                "wins": t.get("won", 0),
                "draws": t.get("drawn", 0),
                "losses": t.get("lost", 0),
                "goals_for": t.get("gf", 0),
                "goals_against": t.get("ga", 0),
                "stage_reached": stage_reached.get(our_team, "Group stage"),
                "assists": row["assists"],
                "xg": row["xg"],
                "possession_pct": row["possession_pct"],
                "as_of_stage": "through quarterfinals",
                "source_id": "fifa_team_stats_2026",
                "retrieved_at": TODAY,
            }
        )

    # ---- 5. Coaches / referees ---------------------------------------------
    coach_rows = []
    for row in coaches:
        our_team = WIKI_TO_OURS.get(row["team"], row["team"])
        code = team_code_by_name.get(our_team, "")
        coach_rows.append(
            {
                "coach_id": f"co_{TOURNAMENT}_{code.lower()}_{short_hash(row['coach_name'])}",
                "team": our_team,
                "team_code": code,
                "coach_name": row["coach_name"],
                "coach_nationality": row.get("coach_nationality") or our_team,
                "source_id": "wiki_squads_2026",
                "retrieved_at": TODAY,
            }
        )

    name_country = re.compile(r"^(.*?) \( (.*?) \)")
    referee_rows = []
    seen_officials = set()
    for row in officials:
        section = row.get("section") or ""
        if section.startswith("Referees"):
            role_fields = [("referee", row.get("Referees") or ""), ("assistant_referee", row.get("Assistant referees") or "")]
        elif section.startswith("Video"):
            values = [v for k, v in row.items() if k not in ("section", "Confederation") and v]
            role_fields = [("video_assistant_referee", values[0] if values else "")]
        else:
            continue
        confederation = row.get("Confederation") or ""
        for role, cell in role_fields:
            for chunk in re.findall(r"([^()]+?) \( ([^()]+?) \)", cell):
                name, country = chunk[0].strip(), chunk[1].strip()
                key = (name, country, role)
                if key in seen_officials:
                    continue
                seen_officials.add(key)
                referee_rows.append(
                    {
                        "official_id": f"ref_{TOURNAMENT}_{short_hash(name, country, role)}",
                        "name": name,
                        "country": country,
                        "role": role,
                        "confederation": confederation,
                        "source_id": "wiki_officials_2026",
                        "retrieved_at": TODAY,
                    }
                )

    # ---- write everything ---------------------------------------------------
    write_csv("players_new_rows.csv", new_player_rows)
    write_csv("squad_entries_new_rows.csv", new_squad_rows)
    write_csv("player_club_at_callup_new_rows.csv", new_callup_rows)
    write_csv("clubs_new_rows_for_review.csv", new_club_rows)
    write_csv("squad_entries_updates.csv", squad_updates)
    write_csv("player_stats.csv", stats_rows)
    write_csv("player_stats_unmatched_for_review.csv", unmatched_stats)
    write_csv("team_stats.csv", team_stats_rows)
    write_csv("world_cup_history_matches.csv", matches)
    write_csv("coaches.csv", coach_rows)
    write_csv("referees.csv", referee_rows)
    write_csv("sources_new_rows.csv", NEW_SOURCES)

    summary = {
        "generated_at": TODAY,
        "new_players": len(new_player_rows),
        "new_clubs_for_review": len(new_club_rows),
        "squad_entry_updates": len(squad_updates),
        "squad_removed": sum(1 for r in squad_updates if r["squad_status"] == "removed"),
        "player_stats_matched": len(stats_rows),
        "player_stats_unmatched": len(unmatched_stats),
        "matches": len(matches),
        "matches_played": sum(1 for m in matches if m["status"] == "played"),
        "team_stats": len(team_stats_rows),
        "coaches": len(coach_rows),
        "officials": len(referee_rows),
    }
    (OUT / "import_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
