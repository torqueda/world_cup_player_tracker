#!/usr/bin/env python3
"""
Apply manual ground-truth corrections from club_triage_manual_checks.md to the
reconciled Step 6 club baseline.

This script:
1. Repairs lingering text-encoding artifacts in club fields.
2. Applies explicit manual field corrections from the "Dataset manual changes"
   section.
3. Applies canonical club-name updates from the "Name changes" section.
4. Rewrites clubs_geocoded_reconciled.csv as the cleaned baseline moving forward.
5. Writes audit artifacts describing what changed and what note lines were skipped.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


BASELINE_FIELDS_TO_CLEAN = ["club_name", "club_name_ascii", "league", "country", "city", "stadium"]

TEXT_REPAIR_REPLACEMENTS = {
    "√©": "é",
    "√≥": "ó",
    "√°": "á",
    "√≠": "í",
    "√±": "ñ",
    "√º": "ú",
    "√∂": "ö",
    "√ß": "ç",
    "≈Ñ": "ń",
    "≈ë": "ő",
    "ƒü": "ğ",
    "ÃÅ": "á",
}

MANUAL_CLUB_KEY_ALIASES = {
    "hamburguersv": "hamburgersv",
    "huracan": "clubatleticohuracan",
    "castellonname": "castellon",
    "fcnordsjllandname": "fcnordsjaelland",
    "ferencvarosname": "ferencvaros",
    "fortunadusseldorfname": "fortunadusseldorf",
    "genclerbirliginame": "genclerbirligi",
    "gyorietoname": "gyorieto",
    "ifknorrkopingname": "ifknorrkoping",
    "juarezname": "juarez",
    "leonname": "leon",
    "lechiagdanskname": "lechiagdansk",
    "marathonname": "marathon",
    "mazatlanname": "mazatlan",
    "pogonszczecinname": "pogonszczecin",
    "standardliegename": "standardliege",
    "stromsgodsetname": "stromsgodset",
    "zurichname": "zurich",
}

NAME_CHANGE_ASSUMPTIONS = {
    "Esteghlal": "Esteghlal F.C.",
    "Newcastle Jets": "Newcastle Jets FC",
    "Middlesbrough": "Middlesbrough F.C.",
}

SPECIAL_CLUB_FIXES = {
    "c_fc_nordsjlland_ae9978cb": {"club_name": "FC Nordsjælland", "city": "Farum"},
    "c_genclerbirligi_22e3fae3": {"club_name": "Gençlerbirliği", "city": "Ankara"},
    "c_gyori_eto_4f17868c": {"club_name": "Győri ETO", "city": "Győr"},
    "c_pogon_szczecin_1d372b0b": {"club_name": "Pogoń Szczecin", "stadium": "Florian Krygier Municipal Stadium"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        default="data/processed/club_geolocation_working/clubs_geocoded_reconciled.csv",
        help="Baseline reconciled clubs CSV to clean in place.",
    )
    parser.add_argument(
        "--manual-notes",
        default="club_triage_manual_checks.md",
        help="Manual notes markdown file containing dataset corrections and name changes.",
    )
    parser.add_argument(
        "--audit-dir",
        default="data/processed/club_geolocation_working",
        help="Directory for audit outputs.",
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


def ascii_fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def to_ascii_name(value: str) -> str:
    return ascii_fold(value).replace("–", "-").replace("—", "-").strip()


def normalize_key(value: str) -> str:
    text = to_ascii_name(repair_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def repair_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text.strip():
        return text.strip()
    text = text.strip()

    if any(marker in text for marker in ["Ã", "Å", "â"]):
        try:
            text = text.encode("latin-1").decode("utf-8")
        except Exception:
            pass

    if any(127 <= ord(ch) <= 159 for ch in text):
        try:
            text = text.encode("latin-1").decode("mac_roman")
        except Exception:
            pass

    for bad, good in TEXT_REPAIR_REPLACEMENTS.items():
        text = text.replace(bad, good)

    text = text.replace("St James’ Park", "St. James' Park")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_row_lookup(rows: List[Dict[str, str]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for row in rows:
        for candidate in [row.get("club_name", ""), row.get("club_name_ascii", "")]:
            key = normalize_key(candidate)
            if key and key not in lookup:
                lookup[key] = row["club_id"]
    return lookup


def resolve_club_id(raw_name: str, lookup: Dict[str, str]) -> str:
    key = normalize_key(raw_name)
    alias_key = MANUAL_CLUB_KEY_ALIASES.get(key, key)
    return lookup.get(alias_key, "")


def parse_manual_sections(markdown_text: str) -> Tuple[List[str], List[str]]:
    dataset_match = re.search(r"# Dataset manual changes:\n\n(.*?)\n# Name changes:", markdown_text, re.S)
    name_match = re.search(r"# Name changes:\n\n(.*)$", markdown_text, re.S)
    if not dataset_match or not name_match:
        raise ValueError("Could not parse manual notes sections.")
    dataset_lines = [repair_text(line) for line in dataset_match.group(1).splitlines() if line.strip()]
    name_lines = [repair_text(line) for line in name_match.group(1).splitlines() if line.strip()]
    return dataset_lines, name_lines


def split_case_insensitive(value: str, marker: str) -> List[str]:
    return re.split(re.escape(marker), value, flags=re.I, maxsplit=1)


def parse_global_league_replacements(dataset_lines: List[str]) -> Dict[str, str]:
    replacements: Dict[str, str] = {}
    for line in dataset_lines:
        match = re.match(r"All league values of (.*?) changed to (.*?)(?:\.)?$", line)
        if not match:
            continue
        old_value = repair_text(match.group(1))
        new_value = repair_text(match.group(2))
        if old_value and new_value:
            old_values = [part.strip() for part in re.split(r"\s+and\s+", old_value) if part.strip()]
            for value in old_values:
                replacements[value] = new_value
    return replacements


def parse_dataset_club_overrides(
    dataset_lines: List[str],
    lookup: Dict[str, str],
) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    overrides: Dict[str, Dict[str, str]] = {}
    unmatched_lines: List[str] = []

    for line in dataset_lines:
        if line.startswith("All league values of "):
            continue

        working_line = line
        if "Found long/lat" in working_line:
            working_line = working_line.split("Found long/lat", 1)[0].strip().rstrip(".")
        working_line = working_line.replace("stadium league changed to", "league changed to")

        tokens = [
            " city value changed to ",
            " city changed to ",
            " country changed to ",
            " league changed to ",
            " stadium changed from ",
            " stadium value ",
            " changed stadium to ",
            " stadium changed to ",
            " changed to ",
        ]
        positions = [(working_line.find(token), token) for token in tokens if working_line.find(token) != -1]
        if not positions:
            continue

        start_index, _ = min(positions)
        club_label = repair_text(working_line[:start_index].strip())
        club_id = resolve_club_id(club_label, lookup)
        if not club_id:
            unmatched_lines.append(line)
            continue

        club_overrides = overrides.setdefault(club_id, {})
        clauses = [repair_text(part.strip().strip(".")) for part in working_line[start_index:].split(",")]

        first_clause = True
        for clause in clauses:
            lower = clause.lower()

            if (
                first_clause
                and " changed to " in clause
                and not any(
                    phrase in lower
                    for phrase in [
                        "city changed to",
                        "city value changed to",
                        "country changed to",
                        "league changed to",
                        "stadium changed to",
                        "stadium changed from",
                        "stadium value",
                        "changed stadium to",
                    ]
                )
            ):
                club_overrides["club_name"] = repair_text(clause.split(" changed to ", 1)[1])
            elif "city value changed to " in lower:
                club_overrides["city"] = repair_text(clause.split("city value changed to ", 1)[1])
            elif "city changed to " in lower:
                club_overrides["city"] = repair_text(clause.split("city changed to ", 1)[1])
            elif lower.startswith("city to "):
                club_overrides["city"] = repair_text(clause.split("city to ", 1)[1])
            elif "country changed to " in lower:
                club_overrides["country"] = repair_text(clause.split("country changed to ", 1)[1])
            elif lower.startswith("country to "):
                club_overrides["country"] = repair_text(clause.split("country to ", 1)[1])
            elif "league changed to " in lower:
                club_overrides["league"] = repair_text(clause.split("league changed to ", 1)[1])
            elif lower.startswith("league to "):
                club_overrides["league"] = repair_text(clause.split("league to ", 1)[1])
            elif "stadium changed from " in lower and " to " in lower:
                club_overrides["stadium"] = repair_text(clause.rsplit(" to ", 1)[1])
            elif "stadium value " in lower and "changed to " in lower:
                parts = split_case_insensitive(clause, "changed to ")
                if len(parts) == 2:
                    club_overrides["stadium"] = repair_text(parts[1])
            elif "changed stadium to " in lower:
                club_overrides["stadium"] = repair_text(clause.split("changed stadium to ", 1)[1])
            elif "stadium changed to " in lower:
                club_overrides["stadium"] = repair_text(clause.split("stadium changed to ", 1)[1])
            elif lower.startswith("stadium to "):
                club_overrides["stadium"] = repair_text(clause.split("stadium to ", 1)[1])

            first_clause = False

    return overrides, unmatched_lines


def parse_name_changes(
    name_lines: List[str],
    rows: List[Dict[str, str]],
) -> Tuple[Dict[str, str], List[str]]:
    lookup = build_row_lookup(rows)
    changes: Dict[str, str] = {}
    unmatched_lines: List[str] = []

    normalized_existing_names = {normalize_key(row["club_name"]): row["club_id"] for row in rows}

    for line in name_lines:
        old_name = ""
        new_name = ""
        if " to " in line:
            old_name, new_name = [repair_text(part) for part in line.split(" to ", 1)]
            if new_name == "F.C.":
                new_name = "Middlesbrough F.C."
        elif line in {"Esteghlal F.C.", "Newcastle Jets FC"}:
            old_name = "Esteghlal" if line == "Esteghlal F.C." else "Newcastle Jets"
            new_name = line
        else:
            unmatched_lines.append(line)
            continue

        club_id = resolve_club_id(old_name, lookup)
        if not club_id and normalize_key(new_name) in normalized_existing_names:
            continue
        if not club_id and old_name in NAME_CHANGE_ASSUMPTIONS:
            new_name = NAME_CHANGE_ASSUMPTIONS[old_name]
            club_id = resolve_club_id(old_name, lookup)
        if not club_id:
            unmatched_lines.append(line)
            continue

        changes[club_id] = new_name

    return changes, unmatched_lines


def main() -> None:
    args = parse_args()
    baseline_path = Path(args.baseline)
    manual_notes_path = Path(args.manual_notes)
    audit_dir = Path(args.audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv(baseline_path)
    fieldnames = list(rows[0].keys())

    baseline_text_repairs = 0
    for row in rows:
        for field in BASELINE_FIELDS_TO_CLEAN:
            original = row.get(field, "")
            repaired = repair_text(original)
            if repaired != original:
                baseline_text_repairs += 1
                row[field] = repaired

    manual_text = manual_notes_path.read_text(encoding="utf-8")
    dataset_lines, name_lines = parse_manual_sections(manual_text)

    global_league_replacements = parse_global_league_replacements(dataset_lines)
    global_replacement_count = 0
    for row in rows:
        league = row.get("league", "")
        repaired_league = global_league_replacements.get(league, league)
        if repaired_league != league:
            row["league"] = repaired_league
            global_replacement_count += 1

    lookup = build_row_lookup(rows)
    club_overrides, unmatched_dataset_lines = parse_dataset_club_overrides(dataset_lines, lookup)

    field_change_audit: List[Dict[str, str]] = []
    club_override_change_count = 0
    for row in rows:
        overrides = club_overrides.get(row["club_id"])
        if not overrides:
            continue
        for field, new_value in overrides.items():
            old_value = row.get(field, "")
            if not new_value or old_value == new_value:
                continue
            row[field] = new_value
            if field == "club_name":
                row["club_name_ascii"] = to_ascii_name(new_value)
            club_override_change_count += 1
            field_change_audit.append(
                {
                    "club_id": row["club_id"],
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "change_source": "dataset_manual_changes",
                }
            )

    for row in rows:
        if row.get("club_name"):
            row["club_name_ascii"] = to_ascii_name(row["club_name"])

    for row in rows:
        special_fixes = SPECIAL_CLUB_FIXES.get(row["club_id"])
        if not special_fixes:
            continue
        for field, new_value in special_fixes.items():
            old_value = row.get(field, "")
            if old_value == new_value:
                continue
            row[field] = new_value
            if field == "club_name":
                row["club_name_ascii"] = to_ascii_name(new_value)
            field_change_audit.append(
                {
                    "club_id": row["club_id"],
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "change_source": "special_club_fixes",
                }
            )

    name_changes, unmatched_name_lines = parse_name_changes(name_lines, rows)
    name_change_count = 0
    for row in rows:
        new_name = name_changes.get(row["club_id"])
        if not new_name or row["club_name"] == new_name:
            continue
        field_change_audit.append(
            {
                "club_id": row["club_id"],
                "field": "club_name",
                "old_value": row["club_name"],
                "new_value": new_name,
                "change_source": "name_changes",
            }
        )
        row["club_name"] = new_name
        row["club_name_ascii"] = to_ascii_name(new_name)
        name_change_count += 1

    write_csv(baseline_path, rows, fieldnames)

    audit_rows = sorted(field_change_audit, key=lambda item: (item["club_id"], item["field"], item["change_source"]))
    write_csv(
        audit_dir / "clubs_geocoded_reconciled_corrections_audit.csv",
        audit_rows,
        ["club_id", "field", "old_value", "new_value", "change_source"],
    )

    skipped_rows = (
        [{"section": "dataset_manual_changes", "line": line} for line in unmatched_dataset_lines]
        + [{"section": "name_changes", "line": line} for line in unmatched_name_lines]
    )
    write_csv(
        audit_dir / "clubs_geocoded_reconciled_skipped_manual_lines.csv",
        skipped_rows,
        ["section", "line"],
    )

    summary_rows = [
        {"metric": "baseline_path", "value": str(baseline_path)},
        {"metric": "baseline_text_repairs", "value": str(baseline_text_repairs)},
        {"metric": "global_league_replacements_applied", "value": str(global_replacement_count)},
        {"metric": "dataset_manual_field_changes_applied", "value": str(club_override_change_count)},
        {"metric": "canonical_name_changes_applied", "value": str(name_change_count)},
        {"metric": "total_audit_rows", "value": str(len(audit_rows))},
        {"metric": "unmatched_dataset_manual_lines", "value": str(len(unmatched_dataset_lines))},
        {"metric": "unmatched_name_change_lines", "value": str(len(unmatched_name_lines))},
    ]
    write_csv(
        audit_dir / "clubs_geocoded_reconciled_corrections_summary.csv",
        summary_rows,
        ["metric", "value"],
    )


if __name__ == "__main__":
    main()
