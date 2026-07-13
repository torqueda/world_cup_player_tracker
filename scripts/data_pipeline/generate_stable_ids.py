#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TEAM_CODES = {
    "Algeria": "ALG",
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bosnia-Herzegovina": "BIH",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Cape Verde": "CPV",
    "Colombia": "COL",
    "Congo DR": "COD",
    "Croatia": "CRO",
    "Curacao": "CUW",
    "Czechia": "CZE",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Germany": "GER",
    "Ghana": "GHA",
    "Haiti": "HAI",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Ivory Coast": "CIV",
    "Japan": "JPN",
    "Jordan": "JOR",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Portugal": "POR",
    "Qatar": "QAT",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "SUI",
    "Tunisia": "TUN",
    "Türkiye": "TUR",
    "United States": "USA",
    "Uruguay": "URU",
    "Uzbekistan": "UZB",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ascii_fold(value: str) -> str:
    value = "" if pd.isna(value) else str(value)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return value


def clean_spaces(value: str) -> str:
    value = "" if pd.isna(value) else str(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify(value: str, max_len: int = 40) -> str:
    value = ascii_fold(clean_spaces(value)).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len].strip("_") or "unknown"


def hash8(*parts: str) -> str:
    joined = "||".join(clean_spaces(str(part)).lower() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]


def normalize_position(value: str) -> str:
    value = clean_spaces(value).lower()
    mapping = {
        "goalkeepers": "goalkeeper",
        "goalkeeper": "goalkeeper",
        "gk": "goalkeeper",
        "defenders": "defender",
        "defender": "defender",
        "df": "defender",
        "midfielders": "midfielder",
        "midfielder": "midfielder",
        "mf": "midfielder",
        "forwards": "forward",
        "forward": "forward",
        "fw": "forward",
    }
    return mapping.get(value, "unknown")


def make_player_id(team_code: str, player_name: str) -> str:
    player_slug = slugify(player_name, max_len=32)
    digest = hash8("player", team_code, ascii_fold(player_name))
    return f"p_{team_code.lower()}_{player_slug}_{digest}"


def make_club_id(club_name: str) -> str:
    club_slug = slugify(club_name, max_len=40)
    digest = hash8("club", ascii_fold(club_name))
    return f"c_{club_slug}_{digest}"


def make_squad_entry_id(team_code: str, player_id: str) -> str:
    digest = hash8("squad_entry", "fifa_world_cup_2026", team_code, player_id)
    return f"se_wc2026_{team_code.lower()}_{digest}"


def make_player_club_callup_id(team_code: str, player_id: str, club_id: str) -> str:
    digest = hash8("player_club_callup", "fifa_world_cup_2026", team_code, player_id, club_id)
    return f"pc_wc2026_{digest}"


def make_source_id(publisher: str, url: str) -> str:
    digest = hash8("source", publisher, url)
    return f"src_{slugify(publisher, max_len=16)}_{digest}"


def build_outputs(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    raw = raw.copy()
    raw = raw.fillna("")

    raw["team"] = raw["team"].map(clean_spaces)
    raw["player_name_raw"] = raw["player_name_raw"].map(clean_spaces)
    raw["club_name_raw"] = raw["club_name_raw"].map(clean_spaces)
    raw["position_group_raw"] = raw["position_group_raw"].map(clean_spaces)

    raw["team_code"] = raw["team"].map(TEAM_CODES)
    missing_codes = sorted(raw.loc[raw["team_code"].isna(), "team"].unique())
    if missing_codes:
        raise ValueError(f"Missing team codes for: {missing_codes}")

    raw["player_id"] = raw.apply(
        lambda r: make_player_id(r["team_code"], r["player_name_raw"]),
        axis=1,
    )

    raw["club_id"] = raw["club_name_raw"].apply(make_club_id)

    raw["squad_entry_id"] = raw.apply(
        lambda r: make_squad_entry_id(r["team_code"], r["player_id"]),
        axis=1,
    )

    raw["player_club_callup_id"] = raw.apply(
        lambda r: make_player_club_callup_id(r["team_code"], r["player_id"], r["club_id"]),
        axis=1,
    )

    verified_at = now_utc()

    players = (
        raw.sort_values(["team_code", "player_name_raw"])
        .drop_duplicates(subset=["player_id"])
        .assign(
            wikidata_id="",
            fifa_id="",
            espn_id="",
            display_name=lambda d: d["player_name_raw"],
            name_ascii=lambda d: d["player_name_raw"].map(ascii_fold),
            date_of_birth="",
            place_of_birth="",
            birth_country="",
            birth_lat="",
            birth_lon="",
            height_cm="",
            primary_position=lambda d: d["position_group_raw"].map(normalize_position),
            image_commons_title="",
            image_url="",
            image_author="",
            image_license="",
            image_source_url="",
            bio_source_url="",
            data_confidence="provisional_raw_import",
            manual_review_flag="FALSE",
            notes="",
        )
    )[
        [
            "player_id",
            "wikidata_id",
            "fifa_id",
            "espn_id",
            "display_name",
            "name_ascii",
            "date_of_birth",
            "place_of_birth",
            "birth_country",
            "birth_lat",
            "birth_lon",
            "height_cm",
            "primary_position",
            "image_commons_title",
            "image_url",
            "image_author",
            "image_license",
            "image_source_url",
            "bio_source_url",
            "data_confidence",
            "manual_review_flag",
            "notes",
        ]
    ]

    squad_entries = raw.assign(
        tournament="fifa_world_cup_2026",
        display_name_at_source=lambda d: d["player_name_raw"],
        position_group=lambda d: d["position_group_raw"].map(normalize_position),
        shirt_number=lambda d: d.get("shirt_number_raw", ""),
        squad_status="active",
        is_replacement="FALSE",
        replaced_player_id="",
        replacement_reason="",
        official_roster_source_url=lambda d: d["source_url"],
        verified_at=verified_at,
    )[
        [
            "squad_entry_id",
            "tournament",
            "team",
            "team_code",
            "player_id",
            "display_name_at_source",
            "position_group",
            "shirt_number",
            "squad_status",
            "is_replacement",
            "replaced_player_id",
            "replacement_reason",
            "official_roster_source_url",
            "verified_at",
        ]
    ]

    clubs = (
        raw.sort_values(["club_name_raw"])
        .drop_duplicates(subset=["club_id"])
        .assign(
            wikidata_id="",
            club_name=lambda d: d["club_name_raw"],
            club_name_ascii=lambda d: d["club_name_raw"].map(ascii_fold),
            country="",
            league="",
            city="",
            stadium="",
            club_lat="",
            club_lon="",
            club_source_url="",
            geo_source="",
            manual_review_flag="FALSE",
            notes="",
        )
    )[
        [
            "club_id",
            "wikidata_id",
            "club_name",
            "club_name_ascii",
            "country",
            "league",
            "city",
            "stadium",
            "club_lat",
            "club_lon",
            "club_source_url",
            "geo_source",
            "manual_review_flag",
            "notes",
        ]
    ]

    player_club_at_callup = raw.assign(
        team=lambda d: d["team"],
        club_name_at_source=lambda d: d["club_name_raw"],
        club_rule="source_listed_club",
        is_on_loan="unknown",
        parent_club_id="",
        loan_club_id="",
        club_source_url=lambda d: d["source_url"],
        confidence="provisional_raw_import",
        notes="",
    )[
        [
            "player_club_callup_id",
            "player_id",
            "club_id",
            "team",
            "club_name_at_source",
            "club_rule",
            "is_on_loan",
            "parent_club_id",
            "loan_club_id",
            "club_source_url",
            "confidence",
            "notes",
        ]
    ]

    source_rows = []
    for _, row in (
        raw[["source_name", "source_url", "source_checked_at"]]
        .drop_duplicates()
        .sort_values(["source_name", "source_url"])
        .iterrows()
    ):
        source_rows.append(
            {
                "source_id": make_source_id(row["source_name"], row["source_url"]),
                "source_type": "roster",
                "publisher": row["source_name"],
                "url": row["source_url"],
                "title": "2026 World Cup squad list bootstrap source",
                "accessed_at": row["source_checked_at"],
                "published_at": "",
                "reliability_tier": "trusted_media",
                "notes": "Bootstrap roster source. Verify roster conflicts against FIFA or national federation sources.",
            }
        )

    sources = pd.DataFrame(source_rows)

    review_rows = []
    review_id_counter = 1

    def add_review(entity_type, entity_id, issue_type, issue_detail, suggested_fix="", source_url="", priority="medium", status="open", notes=""):
        nonlocal review_id_counter
        review_rows.append(
            {
                "review_id": f"rev_{review_id_counter:05d}",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "issue_type": issue_type,
                "issue_detail": issue_detail,
                "suggested_fix": suggested_fix,
                "source_url": source_url,
                "priority": priority,
                "status": status,
                "resolved_at": "",
                "notes": notes,
            }
        )
        review_id_counter += 1

    # Missing values.
    for _, row in raw.iterrows():
        if not row["player_name_raw"]:
            add_review("raw_roster_import", row["raw_roster_id"], "missing_player_name", "Raw roster row has no player name.", priority="high")
        if not row["club_name_raw"]:
            add_review("player_club_at_callup", row["player_club_callup_id"], "missing_club", "Player has no listed club in raw import.", source_url=row["source_url"], priority="high")

    # Duplicate player names within same team.
    dupes = raw.groupby(["team_code", "player_name_raw"]).size().reset_index(name="count")
    dupes = dupes[dupes["count"] > 1]
    for _, row in dupes.iterrows():
        add_review(
            "player",
            "",
            "duplicate_player_name",
            f"{row['player_name_raw']} appears {row['count']} times for {row['team_code']}.",
            "Check whether this is a duplicate row or two different players with the same name.",
            priority="high",
        )

    # Known team count exceptions/warnings.
    team_counts = raw.groupby("team").size().to_dict()
    for team, count in sorted(team_counts.items()):
        if count != 26:
            status = "deferred"
            priority = "medium"
            detail = f"{team} has {count} imported roster rows rather than 26."
            suggested = "Confirm whether this is an intentional source/team exception or a roster issue."
            add_review(
                "squad_entry",
                "",
                "team_count_exception",
                detail,
                suggested,
                priority=priority,
                status=status,
            )

    manual_review_queue = pd.DataFrame(review_rows)

    world_cup_history = pd.DataFrame(
        columns=[
            "history_id",
            "player_id",
            "world_cup_year",
            "team",
            "in_final_squad",
            "appearances",
            "minutes",
            "goals",
            "source_url",
            "manual_review_flag",
            "notes",
        ]
    )

    change_log = pd.DataFrame(
        columns=[
            "change_id",
            "changed_at",
            "team",
            "player_id",
            "change_type",
            "field_changed",
            "old_value",
            "new_value",
            "source_url",
            "reviewed_by",
            "notes",
        ]
    )

    return {
        "players": players,
        "squad_entries": squad_entries,
        "clubs": clubs,
        "player_club_at_callup": player_club_at_callup,
        "sources": sources,
        "manual_review_queue": manual_review_queue,
        "world_cup_history": world_cup_history,
        "change_log": change_log,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Corrected raw_roster_import CSV.")
    parser.add_argument("--outdir", default="step2_outputs", help="Directory for generated CSVs.")
    args = parser.parse_args()

    raw = pd.read_csv(args.input, dtype=str).fillna("")
    outputs = build_outputs(raw)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for name, df in outputs.items():
        path = outdir / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Wrote {path} ({len(df)} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())