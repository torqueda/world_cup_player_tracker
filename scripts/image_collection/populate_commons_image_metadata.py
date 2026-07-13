#!/usr/bin/env python3

"""
Populate Wikimedia Commons image metadata for the players sheet.

Input:
  - players CSV with a populated wikidata_id column.

Output:
  - players_image_metadata_enriched.csv
  - image_metadata_matches.csv
  - image_metadata_review_queue.csv
  - image_metadata_summary.csv

Default behavior:
  - Preserves all existing rows and columns.
  - Uses each player's Wikidata QID to fetch Wikidata image property P18.
  - Uses Wikimedia Commons imageinfo/extmetadata to fetch:
      image_commons_title
      image_url
      image_author
      image_license
      image_source_url
  - Fills blank image-related cells.
  - Does not overwrite existing nonblank image cells unless --overwrite is passed.

Example:
  python populate_commons_image_metadata.py \
    --players "world_cup_2026_player_map_master - players.csv" \
    --outdir step4_image_outputs \
    --contact "your-email@example.com"
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import pandas as pd
import requests


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

IMAGE_COLUMNS = [
    "image_commons_title",
    "image_url",
    "image_author",
    "image_license",
    "image_source_url",
]

REQUIRED_PLAYER_COLUMNS = [
    "player_id",
    "wikidata_id",
    "display_name",
    "image_commons_title",
    "image_url",
    "image_author",
    "image_license",
    "image_source_url",
]


def clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_html(value: str) -> str:
    value = clean(value)
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_qid(value: str) -> str:
    value = clean(value).upper()
    match = re.search(r"Q\d+", value)
    return match.group(0) if match else ""


def normalize_file_title(value: str) -> str:
    value = clean(value)

    if not value:
        return ""

    # Convert direct Commons upload URLs to filenames when possible.
    if "upload.wikimedia.org/" in value:
        value = unquote(value.rstrip("/").split("/")[-1])

    # Convert Commons file-page URLs to filenames when possible.
    if "commons.wikimedia.org/wiki/File:" in value:
        value = unquote(value.split("/wiki/File:", 1)[1])

    value = value.replace("_", " ").strip()

    if not value:
        return ""

    if value.lower().startswith("file:"):
        value = "File:" + value.split(":", 1)[1].strip()
    else:
        value = "File:" + value

    return value


def commons_file_page_url(file_title: str) -> str:
    file_title = normalize_file_title(file_title)
    if not file_title:
        return ""
    filename = file_title.split(":", 1)[1].replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/File:{quote(filename, safe='/:()\',')}"


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_p18_filenames(
    session: requests.Session,
    qids: list[str],
    cache: dict,
    delay: float,
) -> dict[str, str]:
    qids = sorted({normalize_qid(qid) for qid in qids if normalize_qid(qid)})
    missing = [qid for qid in qids if qid not in cache]

    for chunk in chunked(missing, 50):
        params = {
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "props": "claims",
            "format": "json",
        }

        response = session.get(WIKIDATA_API, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        entities = data.get("entities", {})
        for qid in chunk:
            filename = ""
            entity = entities.get(qid, {})
            claims = entity.get("claims", {})
            p18_claims = claims.get("P18", [])

            # Use first P18 claim. If Wikidata has multiple images, later manual review can choose differently.
            if p18_claims:
                mainsnak = p18_claims[0].get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                value = datavalue.get("value", "")
                filename = clean(value)

            cache[qid] = filename

        time.sleep(delay)

    return {qid: cache.get(qid, "") for qid in qids}


def ext_value(extmetadata: dict, key: str) -> str:
    item = extmetadata.get(key, {})
    if isinstance(item, dict):
        return strip_html(item.get("value", ""))
    return ""


def parse_license(extmetadata: dict) -> str:
    for key in ["LicenseShortName", "UsageTerms", "License"]:
        value = ext_value(extmetadata, key)
        if value:
            return value
    return ""


def parse_author(extmetadata: dict, upload_user: str = "") -> str:
    for key in ["Artist", "Credit", "Author"]:
        value = ext_value(extmetadata, key)
        if value:
            return value
    return clean(upload_user)


def fetch_commons_metadata(
    session: requests.Session,
    file_titles: list[str],
    cache: dict,
    delay: float,
) -> dict[str, dict]:
    normalized_titles = sorted({normalize_file_title(title) for title in file_titles if normalize_file_title(title)})
    missing = [title for title in normalized_titles if title not in cache]

    for chunk in chunked(missing, 50):
        params = {
            "action": "query",
            "prop": "imageinfo",
            "titles": "|".join(chunk),
            "iiprop": "url|user|canonicaltitle|extmetadata",
            "format": "json",
            "redirects": "1",
        }

        response = session.get(COMMONS_API, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})

        seen_titles = set()
        for page in pages.values():
            title = normalize_file_title(page.get("title", ""))
            seen_titles.add(title)

            info = {}
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                ii = imageinfo[0]
                ext = ii.get("extmetadata", {})

                canonical_title = normalize_file_title(ii.get("canonicaltitle", "") or page.get("title", ""))
                if not canonical_title:
                    canonical_title = title

                description_url = clean(ii.get("descriptionurl", "")) or commons_file_page_url(canonical_title)

                info = {
                    "image_commons_title": canonical_title,
                    "image_url": clean(ii.get("url", "")),
                    "image_author": parse_author(ext, ii.get("user", "")),
                    "image_license": parse_license(ext),
                    "image_source_url": description_url,
                    "raw_license_url": ext_value(ext, "LicenseUrl"),
                    "raw_object_name": ext_value(ext, "ObjectName"),
                    "raw_credit": ext_value(ext, "Credit"),
                    "raw_artist": ext_value(ext, "Artist"),
                }
            else:
                info = {
                    "image_commons_title": title,
                    "image_url": "",
                    "image_author": "",
                    "image_license": "",
                    "image_source_url": commons_file_page_url(title),
                    "raw_license_url": "",
                    "raw_object_name": "",
                    "raw_credit": "",
                    "raw_artist": "",
                }

            cache[title] = info

        # If Commons did not return a page for a requested title, keep a placeholder.
        for requested in chunk:
            if requested not in seen_titles and requested not in cache:
                cache[requested] = {
                    "image_commons_title": requested,
                    "image_url": "",
                    "image_author": "",
                    "image_license": "",
                    "image_source_url": commons_file_page_url(requested),
                    "raw_license_url": "",
                    "raw_object_name": "",
                    "raw_credit": "",
                    "raw_artist": "",
                }

        time.sleep(delay)

    return {title: cache.get(title, {}) for title in normalized_titles}


def ensure_columns(players: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_PLAYER_COLUMNS if col not in players.columns]
    if missing:
        raise ValueError(f"Missing required columns in players CSV: {missing}")


def append_note(old_note: str, new_note: str) -> str:
    old_note = clean(old_note)
    if not old_note:
        return new_note
    if new_note in old_note:
        return old_note
    return f"{old_note} | {new_note}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", required=True, help="Current players CSV.")
    parser.add_argument("--outdir", default="step4_image_outputs", help="Output directory.")
    parser.add_argument(
        "--contact",
        required=True,
        help="Contact info for Wikimedia User-Agent, e.g. your email or project URL.",
    )
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between API requests.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing image-related cells. Default is to fill blanks only.",
    )
    parser.add_argument(
        "--update-notes",
        action="store_true",
        help="Append a short note when image metadata is filled.",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    cache_dir = outdir / "cache"
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    p18_cache_path = cache_dir / "wikidata_p18_cache.json"
    commons_cache_path = cache_dir / "commons_imageinfo_cache.json"

    p18_cache = load_cache(p18_cache_path)
    commons_cache = load_cache(commons_cache_path)

    players = pd.read_csv(args.players, dtype=str).fillna("")
    ensure_columns(players)

    # Normalize QIDs in-place for consistent API calls.
    players["wikidata_id"] = players["wikidata_id"].map(normalize_qid)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": f"WorldCupPlayerMap/0.1 ({args.contact}) Python requests",
            "Accept": "application/json",
        }
    )

    qids = players["wikidata_id"].dropna().astype(str).tolist()
    p18_by_qid = fetch_p18_filenames(session, qids, p18_cache, args.delay)
    save_cache(p18_cache_path, p18_cache)

    # Determine the file title to use for each player:
    # 1. Existing image_commons_title if present
    # 2. P18 filename from Wikidata
    # 3. Existing image_url if it can be normalized into a filename
    file_title_by_player = {}
    for _, row in players.iterrows():
        player_id = row["player_id"]
        qid = row["wikidata_id"]

        existing_title = normalize_file_title(row.get("image_commons_title", ""))
        p18_title = normalize_file_title(p18_by_qid.get(qid, ""))
        existing_url_title = normalize_file_title(row.get("image_url", ""))

        file_title = existing_title or p18_title or existing_url_title
        file_title_by_player[player_id] = file_title

    file_titles = [title for title in file_title_by_player.values() if title]
    commons_by_title = fetch_commons_metadata(session, file_titles, commons_cache, args.delay)
    save_cache(commons_cache_path, commons_cache)

    enriched = players.copy()
    match_rows = []
    review_rows = []

    filled_counts = {col: 0 for col in IMAGE_COLUMNS}

    for idx, row in enriched.iterrows():
        player_id = row["player_id"]
        display_name = row["display_name"]
        qid = row["wikidata_id"]

        file_title = file_title_by_player.get(player_id, "")
        p18_title = normalize_file_title(p18_by_qid.get(qid, ""))
        metadata = commons_by_title.get(file_title, {}) if file_title else {}

        proposed = {
            "image_commons_title": metadata.get("image_commons_title", "") or file_title,
            "image_url": metadata.get("image_url", ""),
            "image_author": metadata.get("image_author", ""),
            "image_license": metadata.get("image_license", ""),
            "image_source_url": metadata.get("image_source_url", "") or commons_file_page_url(file_title),
        }

        for col in IMAGE_COLUMNS:
            current_value = clean(enriched.at[idx, col])
            new_value = clean(proposed.get(col, ""))
            if new_value and (args.overwrite or not current_value):
                enriched.at[idx, col] = new_value
                filled_counts[col] += 1

        if args.update_notes and file_title and proposed.get("image_source_url"):
            enriched.at[idx, "notes"] = append_note(
                enriched.at[idx, "notes"],
                "Image metadata populated from Wikidata P18/Wikimedia Commons API.",
            )

        match_rows.append(
            {
                "player_id": player_id,
                "display_name": display_name,
                "wikidata_id": qid,
                "wikidata_p18_title": p18_title,
                "metadata_file_title_used": file_title,
                "image_commons_title": proposed.get("image_commons_title", ""),
                "image_url": proposed.get("image_url", ""),
                "image_author": proposed.get("image_author", ""),
                "image_license": proposed.get("image_license", ""),
                "image_source_url": proposed.get("image_source_url", ""),
                "raw_license_url": metadata.get("raw_license_url", ""),
                "raw_artist": metadata.get("raw_artist", ""),
                "raw_credit": metadata.get("raw_credit", ""),
            }
        )

        if not qid:
            review_rows.append(
                {
                    "player_id": player_id,
                    "display_name": display_name,
                    "wikidata_id": qid,
                    "issue_type": "missing_wikidata_id",
                    "issue_detail": "Player has no Wikidata QID, so image lookup was skipped.",
                    "suggested_fix": "Add a Wikidata QID or fill image fields from another licensed source.",
                }
            )
        elif not file_title:
            review_rows.append(
                {
                    "player_id": player_id,
                    "display_name": display_name,
                    "wikidata_id": qid,
                    "issue_type": "no_wikidata_p18_image",
                    "issue_detail": "Wikidata item has no P18 image and no existing image title/url was present.",
                    "suggested_fix": "Leave image fields blank, add a licensed image manually, or check Commons/Wikipedia manually.",
                }
            )
        else:
            missing_parts = [col for col in IMAGE_COLUMNS if not clean(proposed.get(col, ""))]
            if missing_parts:
                review_rows.append(
                    {
                        "player_id": player_id,
                        "display_name": display_name,
                        "wikidata_id": qid,
                        "issue_type": "incomplete_commons_image_metadata",
                        "issue_detail": "Commons metadata missing: " + ", ".join(missing_parts),
                        "suggested_fix": "Open the Commons file page and verify/fill missing attribution or license details manually.",
                    }
                )

    matches = pd.DataFrame(match_rows)
    review = pd.DataFrame(review_rows)

    summary = pd.DataFrame(
        [
            {
                "total_players": len(enriched),
                "players_with_wikidata_id": int(enriched["wikidata_id"].astype(bool).sum()),
                "players_with_image_commons_title": int(enriched["image_commons_title"].astype(bool).sum()),
                "players_with_image_url": int(enriched["image_url"].astype(bool).sum()),
                "players_with_image_author": int(enriched["image_author"].astype(bool).sum()),
                "players_with_image_license": int(enriched["image_license"].astype(bool).sum()),
                "players_with_image_source_url": int(enriched["image_source_url"].astype(bool).sum()),
                "review_items": len(review),
                "filled_image_commons_title_cells": filled_counts["image_commons_title"],
                "filled_image_url_cells": filled_counts["image_url"],
                "filled_image_author_cells": filled_counts["image_author"],
                "filled_image_license_cells": filled_counts["image_license"],
                "filled_image_source_url_cells": filled_counts["image_source_url"],
                "overwrite_mode": bool(args.overwrite),
            }
        ]
    )

    enriched.to_csv(outdir / "players_image_metadata_enriched.csv", index=False, encoding="utf-8-sig")
    matches.to_csv(outdir / "image_metadata_matches.csv", index=False, encoding="utf-8-sig")
    review.to_csv(outdir / "image_metadata_review_queue.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(outdir / "image_metadata_summary.csv", index=False, encoding="utf-8-sig")

    print("Wrote Step 4 image metadata outputs:")
    print(f"- {outdir / 'players_image_metadata_enriched.csv'}")
    print(f"- {outdir / 'image_metadata_matches.csv'}")
    print(f"- {outdir / 'image_metadata_review_queue.csv'}")
    print(f"- {outdir / 'image_metadata_summary.csv'}")
    print()
    print(summary.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
