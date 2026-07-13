#!/usr/bin/env python3
"""
Build a focused text-review queue from the canonical club baseline.

This is meant to support manual cleanup of the real source file
`clubs_geocoded_corrected.csv` before regenerating downstream city artifacts.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


SUGGESTED_FIXES = {
    "c_besiktas_daeca9ad": {
        "club_name_suggested": "Beşiktaş J.K.",
        "city_suggested": "Beşiktaş",
        "stadium_suggested": "Beşiktaş Stadium",
    },
    "c_cracovia_5bed2b4b": {
        "stadium_suggested": "Józef Piłsudski Cracovia Stadium",
    },
    "c_fc_tatran_presov_05bcf723": {
        "club_name_suggested": "FC Tatran Prešov",
        "city_suggested": "Prešov",
    },
    "c_fc_tokyo_9926cea2": {
        "city_suggested": "Chōfu",
    },
    "c_fcsb_dbba85ac": {
        "stadium_suggested": "Arena Națională",
    },
    "c_fenerbahce_58b3ec74": {
        "stadium_suggested": "Şükrü Saracoğlu Stadium",
    },
    "c_genclerbirligi_22e3fae3": {
        "club_name_suggested": "Gençlerbirliği S.K.",
    },
    "c_gyori_eto_4f17868c": {
        "club_name_suggested": "Győri ETO FC",
        "city_suggested": "Győr",
    },
    "c_hradec_kralove_16ceb4be": {
        "stadium_suggested": "Malšovická aréna",
    },
    "c_igdir_afc03fda": {
        "club_name_suggested": "Iğdır F.K.",
        "city_suggested": "Iğdır",
        "stadium_suggested": "Iğdır City Stadium",
    },
    "c_istanbul_basaksehir_eda9bc84": {
        "club_name_suggested": "İstanbul Başakşehir F.K.",
        "city_suggested": "Başakşehir",
        "stadium_suggested": "Başakşehir Fatih Terim Stadium",
    },
    "c_jagiellonia_bialystok_14ff40df": {
        "club_name_suggested": "Jagiellonia Białystok",
        "city_suggested": "Białystok",
        "stadium_suggested": "Stadion Miejski (Białystok)",
    },
    "c_kasmpasa_61344b51": {
        "club_name_suggested": "Kasımpaşa S.K.",
        "stadium_suggested": "Recep Tayyip Erdoğan Stadium",
    },
    "c_lechia_gdansk_6dd6ea20": {
        "club_name_suggested": "Lechia Gdańsk",
        "city_suggested": "Gdańsk",
        "stadium_suggested": "Gdańsk Stadium",
    },
    "c_pogon_szczecin_1d372b0b": {
        "club_name_suggested": "Pogoń Szczecin",
    },
    "c_sigma_olomouc_9866567d": {
        "stadium_suggested": "Andrův stadion",
    },
    "c_slovan_bratislava_8e855156": {
        "club_name_suggested": "ŠK Slovan Bratislava",
    },
    "c_viktoria_plzen_c3cb1557": {
        "club_name_suggested": "FC Viktoria Plzeň",
        "city_suggested": "Plzeň",
    },
    "c_widzew_odz_934a5145": {
        "club_name_suggested": "Widzew Łódź",
        "city_suggested": "Łódź",
        "stadium_suggested": "Widzew Łódź Stadium",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv",
        help="Canonical club baseline CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/club_geolocation_baseline/club_canonical_text_review_queue.csv",
        help="Output review queue CSV.",
    )
    return parser.parse_args()


def is_suspicious(value: str) -> bool:
    if not value:
        return False
    return any(token in value for token in ["_", "�", "√", "Ã"])


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    output_rows: list[dict[str, str]] = []
    for row in rows:
        suspicious_fields = [
            field
            for field in ["club_name", "league", "country", "city", "stadium"]
            if is_suspicious(row.get(field, ""))
        ]
        if not suspicious_fields:
            continue

        suggested = SUGGESTED_FIXES.get(row["club_id"], {})
        output_rows.append(
            {
                "club_id": row["club_id"],
                "suspicious_fields": " | ".join(suspicious_fields),
                "club_name_current": row["club_name"],
                "league_current": row["league"],
                "country_current": row["country"],
                "city_current": row["city"],
                "stadium_current": row["stadium"],
                "club_name_suggested": suggested.get("club_name_suggested", ""),
                "city_suggested": suggested.get("city_suggested", ""),
                "stadium_suggested": suggested.get("stadium_suggested", ""),
            }
        )

    fieldnames = [
        "club_id",
        "suspicious_fields",
        "club_name_current",
        "league_current",
        "country_current",
        "city_current",
        "stadium_current",
        "club_name_suggested",
        "city_suggested",
        "stadium_suggested",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Read {len(rows)} canonical club rows from {input_path}")
    print(f"Wrote {len(output_rows)} text-review rows to {output_path}")


if __name__ == "__main__":
    main()
