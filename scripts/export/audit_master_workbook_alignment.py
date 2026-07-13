#!/usr/bin/env python3
"""
Audit the current master workbook against the canonical club baseline.

This produces a compact machine-readable summary plus a small player birthplace
review file for possible city-name alignment work. The audit is intentionally
non-destructive and does not modify the workbook.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from workbook_rows import read_sheet_rows

REPO_ROOT = Path(__file__).resolve().parents[2]

KNOWN_OLD_TO_CURRENT_CLUB_IDS = {
    "c_psg_7fc479b7": "c_paris_saint_germain_e38062ac",
}

CLUB_CANONICAL_FIELDS = [
    "club_name",
    "club_name_ascii",
    "league",
    "country",
    "city",
    "stadium",
]

GENERIC_LOCATION_TOKENS = {
    "city",
    "county",
    "department",
    "district",
    "governorate",
    "metropolitan",
    "municipality",
    "province",
    "region",
    "state",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--master-workbook",
        default=str(REPO_ROOT / "data/master/world_cup_2026_player_map_master.xlsx"),
        help="Current master workbook.",
    )
    parser.add_argument(
        "--club-baseline",
        default=str(REPO_ROOT / "data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv"),
        help="Canonical club baseline CSV.",
    )
    parser.add_argument(
        "--summary-output",
        default=str(REPO_ROOT / "data/processed/master_exports/master_workbook_alignment_summary.json"),
        help="JSON path for the audit summary.",
    )
    parser.add_argument(
        "--birthplace-review-output",
        default=str(REPO_ROOT / "data/processed/master_exports/player_birthplace_city_candidate_review.csv"),
        help="CSV path for possible player birthplace/city naming review candidates.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with a non-zero status if any integrity check fails.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def repo_relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def fold_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold().strip()


def simplified_text(value: str) -> str:
    return fold_text(value).replace("-", " ").replace(",", " ")


def stripped_place_name(value: str) -> str:
    tokens = [token for token in re.split(r"\s+", simplified_text(value)) if token]
    stripped = [token for token in tokens if token not in GENERIC_LOCATION_TOKENS]
    return " ".join(stripped).strip()


def is_token_prefix(shorter: str, longer: str) -> bool:
    shorter_tokens = [token for token in shorter.split(" ") if token]
    longer_tokens = [token for token in longer.split(" ") if token]
    if not shorter_tokens or not longer_tokens:
        return False
    if len(shorter_tokens) >= len(longer_tokens):
        return False
    return longer_tokens[: len(shorter_tokens)] == shorter_tokens


def find_birthplace_review_candidates(
    players: list[dict[str, object]],
    clubs: list[dict[str, object]],
) -> list[dict[str, object]]:
    club_cities_by_country: dict[str, set[str]] = {}
    for club in clubs:
        country = str(club.get("country") or "").strip()
        city = str(club.get("city") or "").strip()
        if country and city:
            club_cities_by_country.setdefault(country, set()).add(city)

    candidates: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()

    for player in players:
        country = str(player.get("birth_country") or "").strip()
        city = str(player.get("place_of_birth") or "").strip()
        if not country or not city:
            continue

        country_cities = club_cities_by_country.get(country, set())
        if city in country_cities:
            continue

        city_simple = stripped_place_name(city)
        if not city_simple:
            continue
        for club_city in country_cities:
            club_city_simple = stripped_place_name(club_city)
            if not club_city_simple:
                continue
            if city_simple == club_city_simple:
                review_reason = "generic location suffix removed produced a canonical city-name match"
            elif is_token_prefix(city_simple, club_city_simple):
                review_reason = "player birthplace is a contained variant of a canonical club city"
            elif is_token_prefix(club_city_simple, city_simple):
                review_reason = "canonical club city is a contained variant of the player birthplace"
            else:
                continue

            key = (country, city, club_city)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "player_id": player.get("player_id"),
                    "display_name": player.get("display_name"),
                    "birth_country": country,
                    "place_of_birth": city,
                    "candidate_club_city": club_city,
                    "normalized_player_birthplace": city_simple,
                    "normalized_candidate_club_city": club_city_simple,
                    "review_reason": review_reason,
                }
            )

    candidates.sort(
        key=lambda row: (
            str(row["birth_country"]),
            str(row["place_of_birth"]),
            str(row["candidate_club_city"]),
        )
    )
    return candidates


def main() -> None:
    args = parse_args()
    workbook_path = Path(args.master_workbook)

    players = read_sheet_rows(workbook_path, "players")
    clubs = read_sheet_rows(workbook_path, "clubs")
    player_club_at_callup = read_sheet_rows(workbook_path, "player_club_at_callup")
    club_baseline = read_csv_rows(Path(args.club_baseline))

    club_ids = [str(row.get("club_id") or "") for row in clubs if row.get("club_id")]
    club_id_set = set(club_ids)
    player_club_ids = [str(row.get("club_id") or "") for row in player_club_at_callup if row.get("club_id")]
    player_ids = [str(row.get("player_id") or "") for row in players if row.get("player_id")]
    nonblank_wikidata_ids = [str(row.get("wikidata_id") or "") for row in players if row.get("wikidata_id")]

    baseline_by_id = {str(row["club_id"]): row for row in club_baseline}
    baseline_diffs: list[dict[str, object]] = []
    clubs_not_in_baseline: list[str] = []
    for club in clubs:
        club_id = str(club.get("club_id") or "")
        baseline_row = baseline_by_id.get(club_id)
        if not baseline_row:
            # Clubs added after the geocoding baseline (e.g. late roster
            # replacements) are expected; report them without failing.
            clubs_not_in_baseline.append(club_id)
            continue
        for field in CLUB_CANONICAL_FIELDS:
            workbook_value = str(club.get(field) or "")
            baseline_value = str(baseline_row.get(field) or "")
            if workbook_value != baseline_value:
                baseline_diffs.append(
                    {
                        "club_id": club_id,
                        "field": field,
                        "workbook_value": workbook_value,
                        "baseline_value": baseline_value,
                    }
                )

    missing_player_club_ids = sorted(set(player_club_ids) - club_id_set)
    lingering_old_club_ids = {
        old_id: current_id
        for old_id, current_id in KNOWN_OLD_TO_CURRENT_CLUB_IDS.items()
        if old_id in club_id_set or old_id in player_club_ids
    }

    duplicate_wikidata_ids = sorted(
        wikidata_id
        for wikidata_id, count in Counter(nonblank_wikidata_ids).items()
        if count > 1
    )

    birthplace_review_candidates = find_birthplace_review_candidates(players, clubs)
    review_fieldnames = [
        "player_id",
        "display_name",
        "birth_country",
        "place_of_birth",
        "candidate_club_city",
        "normalized_player_birthplace",
        "normalized_candidate_club_city",
        "review_reason",
    ]
    write_csv(Path(args.birthplace_review_output), birthplace_review_candidates, review_fieldnames)

    summary = {
        "source_workbook": repo_relative(workbook_path),
        "club_baseline": repo_relative(args.club_baseline),
        "counts": {
            "players": len(players),
            "clubs": len(clubs),
            "player_club_at_callup": len(player_club_at_callup),
            "unique_player_ids": len(set(player_ids)),
            "unique_club_ids": len(club_id_set),
            "unique_player_club_ids": len(set(player_club_ids)),
        },
        "checks": {
            "player_ids_unique": len(player_ids) == len(set(player_ids)),
            "duplicate_nonblank_player_wikidata_ids": duplicate_wikidata_ids,
            "player_club_ids_missing_from_clubs": missing_player_club_ids,
            "clubs_matching_canonical_baseline": len(baseline_diffs) == 0,
            "club_baseline_diffs": baseline_diffs,
            "clubs_not_in_baseline_pending_geocoding": clubs_not_in_baseline,
            "lingering_known_old_club_ids_in_current_master": lingering_old_club_ids,
        },
        "birthplace_city_review": {
            "exact_player_birthplace_vs_club_city_overlaps": len(
                {
                    str(player.get("place_of_birth") or "")
                    for player in players
                    if player.get("place_of_birth")
                }
                & {
                    str(club.get("city") or "")
                    for club in clubs
                    if club.get("city")
                }
            ),
            "candidate_review_row_count": len(birthplace_review_candidates),
            "candidate_review_output": repo_relative(args.birthplace_review_output),
        },
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote audit summary to {summary_path}")
    print(f"Wrote birthplace review candidates to {args.birthplace_review_output}")
    print(f"Current master clubs: {len(clubs)} | player-club rows: {len(player_club_at_callup)}")
    print(f"Baseline diffs: {len(baseline_diffs)} | missing player-club IDs: {len(missing_player_club_ids)}")
    if clubs_not_in_baseline:
        print(f"Clubs pending geocoding (not in baseline, not a failure): {len(clubs_not_in_baseline)}")
    print(f"Birthplace review candidates: {len(birthplace_review_candidates)}")

    integrity_failures = []
    if not summary["checks"]["player_ids_unique"]:
        integrity_failures.append("player_ids_unique")
    if duplicate_wikidata_ids:
        integrity_failures.append("duplicate_nonblank_player_wikidata_ids")
    if missing_player_club_ids:
        integrity_failures.append("player_club_ids_missing_from_clubs")
    if baseline_diffs:
        integrity_failures.append("club_baseline_diffs")
    if lingering_old_club_ids:
        integrity_failures.append("lingering_known_old_club_ids_in_current_master")

    if integrity_failures:
        print(f"Integrity checks FAILED: {', '.join(integrity_failures)}")
        if args.strict:
            sys.exit(1)
    else:
        print("All integrity checks passed.")


if __name__ == "__main__":
    main()
