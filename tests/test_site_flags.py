"""The site draws a flag next to the country names it shows.

site/src/components/country-flag.tsx looks each name up in
site/src/lib/flags/country-codes.json and loads site/public/flags/<code>.svg.
A name missing from the map shows a letter badge instead of a flag, and a
missing file shows a broken image, so both are checked against the exports.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO / "data" / "processed" / "app_exports"
FLAG_DIR = REPO / "site" / "public" / "flags"
CODES: dict[str, str] = json.loads(
    (REPO / "site" / "src" / "lib" / "flags" / "country-codes.json").read_text(encoding="utf-8")
)

# The fields whose values the site passes to CountryFlag.
FLAG_FIELDS = {
    "teams": ["team"],
    "players": ["birth_country"],
    "clubs": ["country"],
    "cities": ["country"],
}


def test_every_country_shown_with_a_flag_is_mapped() -> None:
    names: set[str] = set()
    for table, fields in FLAG_FIELDS.items():
        for row in json.loads((EXPORT_DIR / f"{table}.json").read_text(encoding="utf-8")):
            names.update(row[field].strip() for field in fields if row.get(field))
    missing = sorted(name for name in names if name not in CODES)
    assert not missing, f"no flag mapped for: {missing}"


def test_every_mapped_flag_has_its_file() -> None:
    missing = sorted({code for code in CODES.values() if not (FLAG_DIR / f"{code}.svg").is_file()})
    assert not missing, f"flag files missing from site/public/flags: {missing}"
