#!/usr/bin/env python3
"""
Apply approved Step 5 alias-club ID remaps so Step 5 final outputs align with the
canonical club IDs already used in the reconciled Step 6 geocoded clubs table.

This script is non-destructive. It does not edit existing files in place.

Outputs:
- approved_club_id_alias_resolution.csv
- clubs_final_for_master_club_id_reconciled.csv
- player_club_at_callup_final_for_master_club_id_reconciled.csv
- player_club_club_id_changes_audit.csv
- club_id_reconciliation_summary.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List


APPROVED_ALIAS_TARGETS = {
    "c_al_etiffaq_f2058dce": "Al-Ettifaq Club",
    "c_heart_of_midlothian_d14abfe8": "Heart of Midlothian F.C.",
    "c_kasimpasa_520d5e13": "Kasımpaşa S.K.",
    "c_leeds_d537b1a4": "Leeds United F.C.",
    "c_mainz_0f856462": "Mainz 05",
    "c_man_united_e54449db": "Manchester United",
    "c_tottehham_6d832957": "Tottenham Hotspur",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clubs-final",
        default="data/processed/club_normalization_final/clubs_final_for_master.csv",
        help="Step 5 final clubs file.",
    )
    parser.add_argument(
        "--player-club",
        default="data/processed/club_normalization_final/player_club_at_callup_final_for_master.csv",
        help="Step 5 final player-club join file.",
    )
    parser.add_argument(
        "--geocoded-clubs",
        default="data/processed/club_geolocation_working/clubs_geocoded_reconciled.csv",
        help="Canonical Step 6 geocoded clubs file used to resolve target IDs by club name.",
    )
    parser.add_argument(
        "--outdir",
        default="data/processed/club_id_reconciliation",
        help="Directory for non-destructive remap outputs.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_target_name_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        name = row.get("club_name", "").strip()
        if not name:
            continue
        if name in index:
            raise ValueError(f"Target club name is not unique in geocoded file: {name}")
        index[name] = row
    return index


def main() -> None:
    args = parse_args()
    clubs_final_path = Path(args.clubs_final)
    player_club_path = Path(args.player_club)
    geocoded_path = Path(args.geocoded_clubs)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    clubs_final_rows = read_csv(clubs_final_path)
    player_club_rows = read_csv(player_club_path)
    geocoded_rows = read_csv(geocoded_path)

    clubs_final_by_id = {row["club_id"]: row for row in clubs_final_rows}
    geocoded_name_index = build_target_name_index(geocoded_rows)
    geocoded_ids = {row["club_id"] for row in geocoded_rows}

    approved_resolution_rows: List[Dict[str, str]] = []
    source_to_target_id: Dict[str, str] = {}

    for source_id, target_name in APPROVED_ALIAS_TARGETS.items():
        if source_id not in clubs_final_by_id:
            raise ValueError(f"Source alias club_id missing from clubs_final: {source_id}")
        if target_name not in geocoded_name_index:
            raise ValueError(f"Target club_name missing from geocoded clubs: {target_name}")

        source_row = clubs_final_by_id[source_id]
        target_row = geocoded_name_index[target_name]
        target_id = target_row["club_id"]

        source_to_target_id[source_id] = target_id

        approved_resolution_rows.append(
            {
                "source_club_id": source_id,
                "source_club_name": source_row.get("club_name", ""),
                "target_club_id": target_id,
                "target_club_name": target_row.get("club_name", ""),
                "target_present_in_geocoded": "TRUE",
                "target_present_in_step5_final": "TRUE" if target_id in clubs_final_by_id else "FALSE",
                "player_club_rows_reassigned": str(sum(1 for row in player_club_rows if row["club_id"] == source_id)),
            }
        )

    remapped_player_rows: List[Dict[str, str]] = []
    player_change_audit_rows: List[Dict[str, str]] = []
    player_rows_changed = 0

    for row in player_club_rows:
        new_row = dict(row)
        old_club_id = row["club_id"]
        new_club_id = source_to_target_id.get(old_club_id, old_club_id)
        new_row["club_id"] = new_club_id
        remapped_player_rows.append(new_row)

        if new_club_id != old_club_id:
            player_rows_changed += 1
            player_change_audit_rows.append(
                {
                    "player_club_callup_id": row.get("player_club_callup_id", ""),
                    "player_id": row.get("player_id", ""),
                    "team": row.get("team", ""),
                    "club_name_at_source": row.get("club_name_at_source", ""),
                    "old_club_id": old_club_id,
                    "new_club_id": new_club_id,
                    "new_canonical_club_name": geocoded_name_index[APPROVED_ALIAS_TARGETS[old_club_id]].get(
                        "club_name", ""
                    ),
                }
            )

    reconciled_clubs_final_rows = [
        dict(row)
        for row in clubs_final_rows
        if row["club_id"] not in source_to_target_id
    ]

    reconciled_clubs_final_ids = {row["club_id"] for row in reconciled_clubs_final_rows}
    remapped_player_ids = {row["club_id"] for row in remapped_player_rows}
    missing_from_reconciled_clubs = sorted(remapped_player_ids - reconciled_clubs_final_ids)
    missing_from_geocoded = sorted(remapped_player_ids - geocoded_ids)

    if missing_from_reconciled_clubs:
        raise ValueError(
            "Remapped player_club file still contains club_ids absent from reconciled Step 5 clubs: "
            + ", ".join(missing_from_reconciled_clubs[:20])
        )
    if missing_from_geocoded:
        raise ValueError(
            "Remapped player_club file still contains club_ids absent from reconciled geocoded clubs: "
            + ", ".join(missing_from_geocoded[:20])
        )

    summary_rows = [
        {"metric": "approved_alias_rows", "value": str(len(approved_resolution_rows))},
        {"metric": "clubs_final_original_rows", "value": str(len(clubs_final_rows))},
        {"metric": "clubs_final_reconciled_rows", "value": str(len(reconciled_clubs_final_rows))},
        {"metric": "player_club_original_rows", "value": str(len(player_club_rows))},
        {"metric": "player_club_rows_with_changed_club_id", "value": str(player_rows_changed)},
        {"metric": "distinct_player_club_club_ids_after_remap", "value": str(len(remapped_player_ids))},
        {"metric": "distinct_geocoded_club_ids", "value": str(len(geocoded_ids))},
        {
            "metric": "all_remapped_player_club_ids_exist_in_reconciled_clubs_final",
            "value": "TRUE" if not missing_from_reconciled_clubs else "FALSE",
        },
        {
            "metric": "all_remapped_player_club_ids_exist_in_geocoded_clubs",
            "value": "TRUE" if not missing_from_geocoded else "FALSE",
        },
    ]

    write_csv(
        outdir / "approved_club_id_alias_resolution.csv",
        approved_resolution_rows,
        [
            "source_club_id",
            "source_club_name",
            "target_club_id",
            "target_club_name",
            "target_present_in_geocoded",
            "target_present_in_step5_final",
            "player_club_rows_reassigned",
        ],
    )
    write_csv(
        outdir / "clubs_final_for_master_club_id_reconciled.csv",
        reconciled_clubs_final_rows,
        list(clubs_final_rows[0].keys()),
    )
    write_csv(
        outdir / "player_club_at_callup_final_for_master_club_id_reconciled.csv",
        remapped_player_rows,
        list(player_club_rows[0].keys()),
    )
    write_csv(
        outdir / "player_club_club_id_changes_audit.csv",
        player_change_audit_rows,
        [
            "player_club_callup_id",
            "player_id",
            "team",
            "club_name_at_source",
            "old_club_id",
            "new_club_id",
            "new_canonical_club_name",
        ],
    )
    write_csv(outdir / "club_id_reconciliation_summary.csv", summary_rows, ["metric", "value"])


if __name__ == "__main__":
    main()
