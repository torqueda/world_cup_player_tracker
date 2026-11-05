#!/usr/bin/env python3
"""
Data fixes from the 2026-11-05 review, applied to the master workbook.

Writes a backup next to the workbook first (git ignores it), then:

1. Corrects four wrong-person Wikidata matches: Alisson, Liam Kelly, Ross
   Stewart and Jorge Sánchez. In each case the matcher picked a namesake whose
   birth date and position disagree with Wikipedia's final squad. The player
   row takes the right entity's QID, birth date, birthplace and photo (or no
   photo when that entity has none).
2. Corrects the name of Iran's number 19, which ESPN's squad list printed as
   "Ali Nemati Omid Noorafkan". He is Ali Nemati. The player_id stays.
3. Cleans the sources registry: removes five club corrections that had been
   pasted into it with shifted columns (each one is already in change_log),
   and registers the other sources the pipeline used.
4. Adds players.match_method (auto, dob or manual) to every row. The
   data_confidence column keeps the matcher's first verdict, which reads as
   unresolved for the players who were matched by hand.
5. Points each URL cell's hyperlink in players at the URL it shows. For the
   late replacements, bio_source_url showed the Wikidata URL but linked to
   Wikipedia's squads page.
6. Appends one change_log row per fix.

Every fix checks the workbook's current value before changing it, so a second
run changes nothing.

Usage:
    python scripts/data_pipeline/apply_2026_11_data_fixes.py
    python scripts/export/refresh_all_exports.py
"""

from __future__ import annotations

import csv
import re
import shutil
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, range_boundaries

REPO_ROOT = Path(__file__).resolve().parents[2]
WB_PATH = REPO_ROOT / "data/master/world_cup_2026_player_map_master.xlsx"
WIKIPEDIA_SQUADS = REPO_ROOT / "data/processed/final_roster_reconciliation/wikipedia_final_squads.csv"
FIX_DATE = "2026-11-05"
SQUADS_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
ESPN_URL = "https://www.espn.com/soccer/story/_/id/48757621/2026-world-cup-squad-lists-players-announced-all-48-teams"
REVIEWED_BY = "user+claude"

IMAGE_FIELDS = ("image_commons_title", "image_url", "image_author", "image_license", "image_source_url")
LINKED_FIELDS = {"image_url", "image_source_url", "bio_source_url"}  # players columns whose cells are hyperlinks


@dataclass(frozen=True)
class IdentityFix:
    player_id: str
    team: str
    squad_name: str  # the name in Wikipedia's final squad
    old_qid: str
    old_entity: str  # who the wrongly matched entity is
    new_qid: str
    date_of_birth: str
    place_of_birth: str
    birth_country: str
    squad_description: str  # how Wikipedia's final squad describes the player
    image: tuple[str, str, str, str, str] | None  # IMAGE_FIELDS values, or None for no photo


# The right entity for the first three is a lower-ranked candidate in the
# matcher's own cache (player_wikidata_matching/wikidata_candidate_matches.csv),
# with the birth date, position and club that Wikipedia's final squad gives.
# Jorge Sánchez's right entity was not among the candidates: Q24034870 is the
# Wikidata item that DBpedia links to the English Wikipedia article
# "Jorge Sánchez (footballer, born 1997)".
IDENTITY_FIXES = (
    IdentityFix(
        player_id="p_bra_alisson_94f708d4",
        team="Brazil",
        squad_name="Alisson",
        old_qid="Q4727251",
        old_entity="a midfielder born 1993-06-25",
        new_qid="Q18237361",
        date_of_birth="1992-10-02",
        place_of_birth="Novo Hamburgo",
        birth_country="Brazil",
        squad_description="a Liverpool goalkeeper born 1992-10-02",
        # Q18237361's photo. Author and licence as on the five other files of
        # this Commons series already in the dataset (Casemiro, Danilo, Neymar,
        # David Alaba, Marko Arnautovic).
        image=(
            "File:20180610 FIFA Friendly Match Austria vs. Brazil 850 1625.jpg",
            "http://commons.wikimedia.org/wiki/Special:FilePath/"
            "20180610%20FIFA%20Friendly%20Match%20Austria%20vs.%20Brazil%20850%201625.jpg",
            "Granada",
            "CC BY-SA 4.0",
            "https://commons.wikimedia.org/wiki/File:20180610_FIFA_Friendly_Match_Austria_vs._Brazil_850_1625.jpg",
        ),
    ),
    IdentityFix(
        player_id="p_sco_liam_kelly_c1331bc4",
        team="Scotland",
        squad_name="Liam Kelly",
        old_qid="Q772315",
        old_entity="a midfielder born 1990-02-10",
        new_qid="Q27448075",
        date_of_birth="1996-01-23",
        place_of_birth="Glasgow",
        birth_country="Scotland",
        squad_description="a Rangers goalkeeper born 1996-01-23",
        image=None,  # Q27448075 has no photo; the old one shows the other Liam Kelly
    ),
    IdentityFix(
        player_id="p_sco_ross_stewart_10079e43",
        team="Scotland",
        squad_name="Ross Stewart",
        old_qid="Q16237030",
        old_entity="a goalkeeper born 1995-04-16",
        new_qid="Q47126518",
        date_of_birth="1996-07-11",
        place_of_birth="Irvine",
        birth_country="Scotland",
        squad_description="a Southampton forward born 1996-07-11",
        image=None,
    ),
    IdentityFix(
        player_id="p_mex_jorge_sanchez_f9fdad59",
        team="Mexico",
        squad_name="Jorge Sánchez",
        old_qid="Q11073995",
        old_entity="a midfielder born 1993-02-14",
        new_qid="Q24034870",
        date_of_birth="1997-12-10",
        place_of_birth="Torreón",
        birth_country="Mexico",
        squad_description="a PAOK defender born 1997-12-10",
        image=None,
    ),
)

NAME_FIX = {
    "player_id": "p_irn_ali_nemati_omid_noorafkan_f6768b31",
    "team": "Iran",
    "old_name": "Ali Nemati Omid Noorafkan",
    "new_name": "Ali Nemati",
}

# Rows that hold club corrections, not sources. Columns are shifted: the
# player_id sits under source_type, the old club_id under title and the new
# club_id under published_at.
MISPLACED_SOURCE_IDS = ("club_corr_0001", "club_corr_0002", "club_corr_0003", "club_corr_0004", "club_corr_0005")

# source_id, source_type, publisher, url, title, accessed_at, published_at, reliability_tier, notes
NEW_SOURCES = (
    (
        "espn_squads_2026", "roster", "ESPN", ESPN_URL,
        "2026 World Cup: Squad lists for all 48 teams", "2026-06-08", "2026-06-03", "secondary",
        "First roster import (raw_roster_import): players, clubs and position groups for all 48 squads, "
        "later reconciled with Wikipedia's final squads. Also the bio source for the one player with no "
        "Wikidata entry. Snapshot: data/raw/espn_rosters_snapshot.html",
    ),
    (
        "wikidata", "biography", "Wikidata", "https://www.wikidata.org/",
        "Wikidata", "2026-07-12", "", "secondary",
        "Player identity (wikidata_id), date and place of birth, and the link to each player's photo; "
        "bio_source_url links each player's entry. Last used for the 2026-07-12 enrichment. Licence: CC0.",
    ),
    (
        "wikimedia_commons", "image", "Wikimedia Commons", "https://commons.wikimedia.org/",
        "Wikimedia Commons", "", "", "secondary",
        "Player photos, found through each player's Wikidata entry. Each file's author, licence and page "
        "are in the players sheet (image_author, image_license, image_source_url).",
    ),
    (
        "geonames", "club_location", "GeoNames", "https://www.geonames.org/",
        "GeoNames geographical database", "", "", "secondary",
        "Club city coordinates (city_lat, city_lon). Each club's city_source_url links its GeoNames "
        "record. Licence: CC BY 4.0.",
    ),
    (
        "wiki_club_articles", "manual_verification", "Wikipedia", "https://en.wikipedia.org/",
        "Wikipedia club articles", "", "", "secondary",
        "Read by hand to correct club details, such as Gaziantep F.K.'s league "
        "(change_log chg_2026-07-13_gaziantep_league). Licence: CC BY-SA 4.0.",
    ),
    (
        "transfermarkt_profiles", "manual_verification", "Transfermarkt", "https://www.transfermarkt.com/",
        "Transfermarkt player profiles", "", "", "secondary",
        "Read by hand to confirm three players' clubs (change_log chg_step5_0003, chg_step5_0004 and "
        "chg_step5_0006). Not scraped.",
    ),
    (
        "rangers_fc_site", "manual_verification", "Rangers F.C.", "https://www.rangers.co.uk/",
        "Rangers F.C. official website", "", "", "primary_official",
        "Signing announcement read by hand to confirm Lawrence Shankland's club "
        "(change_log chg_step5_0002).",
    ),
)

MATCH_METHOD = "match_method"
FIRST_AUTO_MATCH = re.compile(r"Auto-matched to Wikidata (Q\d+)")


def match_method(data_confidence: str, notes: str, wikidata_id: str) -> str:
    """How the player's identity match was settled: auto, dob or manual.

    auto: the matcher's high-confidence pick, never changed since.
    dob: a late replacement matched by name and confirmed by birth date.
    manual: settled by hand, including auto matches corrected later.
    """
    if data_confidence == "wikidata_dob_match":
        return "dob"
    first = FIRST_AUTO_MATCH.search(notes)
    if data_confidence == "wikidata_auto_match_high" and first and first.group(1) == wikidata_id:
        return "auto"
    return "manual"


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def append_note(existing: object, note: str) -> str:
    current = text(existing)
    if not current:
        return note
    return f"{current}{'' if current.endswith('.') else '.'} {note}"


def iso_date(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return text(value)[:10]


class Sheet:
    """Header-addressed access to a worksheet's rows."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.headers = [cell.value for cell in ws[1]]
        self.col = {name: index for index, name in enumerate(self.headers) if name}

    def rows(self):
        for row in self.ws.iter_rows(min_row=2):
            if text(row[0].value):
                yield row

    def get(self, row, name: str) -> object:
        return row[self.col[name]].value

    def set(self, row, name: str, value: object) -> None:
        cell = row[self.col[name]]
        cell.value = value
        if cell.hyperlink is not None or name in LINKED_FIELDS:
            # URL cells link to their own value. A stale link would also bring a
            # cleared value back when the workbook is next opened.
            cell.hyperlink = value if isinstance(value, str) and value.startswith("http") else None

    def find(self, name: str, value: str):
        for row in self.rows():
            if text(self.get(row, name)) == value:
                return row
        raise SystemExit(f"{self.ws.title}: no row with {name} = {value!r}")


def wikipedia_squad_row(team: str, name: str) -> dict[str, str]:
    with WIKIPEDIA_SQUADS.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["team"] == team and row["player_name"] == name:
                return row
    raise SystemExit(f"{team} {name!r} is not in {WIKIPEDIA_SQUADS.name}")


def change_row(change_id: str, team: str, player_id: str, change_type: str, field: str,
               old: str, new: str, source_url: str, notes: str) -> list[object]:
    return [change_id, FIX_DATE, team, player_id, change_type, field, old, new, source_url, REVIEWED_BY, notes]


def fix_identities(players: Sheet) -> list[list[object]]:
    changes = []
    for fix in IDENTITY_FIXES:
        squad = wikipedia_squad_row(fix.team, fix.squad_name)
        if squad["date_of_birth"] != fix.date_of_birth:
            raise SystemExit(
                f"{fix.player_id}: Wikipedia's final squad gives {squad['date_of_birth']}, "
                f"not {fix.date_of_birth}; not changing the row"
            )
        row = players.find("player_id", fix.player_id)
        current = text(players.get(row, "wikidata_id"))
        if current == fix.new_qid:
            continue
        if current != fix.old_qid:
            raise SystemExit(f"{fix.player_id}: expected wikidata_id {fix.old_qid}, found {current!r}; not changing it")

        old_values = (
            f"{fix.old_qid} / {iso_date(players.get(row, 'date_of_birth'))} / "
            f"{text(players.get(row, 'place_of_birth'))}, {text(players.get(row, 'birth_country'))} / "
            f"{text(players.get(row, 'image_commons_title')) or 'no photo'}"
        )
        players.set(row, "wikidata_id", fix.new_qid)
        players.set(row, "date_of_birth", datetime.fromisoformat(fix.date_of_birth))
        players.set(row, "place_of_birth", fix.place_of_birth)
        players.set(row, "birth_country", fix.birth_country)
        players.set(row, "bio_source_url", f"https://www.wikidata.org/wiki/{fix.new_qid}")
        had_photo = bool(text(players.get(row, "image_commons_title")))
        if fix.image:
            photo = f" Photo now {fix.new_qid}'s."
        elif had_photo:
            photo = f" Photo removed: it was {fix.old_qid}'s, and {fix.new_qid} has none."
        else:
            photo = ""
        note = (
            f"QID corrected on {FIX_DATE} from {fix.old_qid} ({fix.old_entity}) to {fix.new_qid}: "
            f"Wikipedia's final squad lists {fix.squad_name} as {fix.squad_description}.{photo}"
        )
        players.set(row, "notes", append_note(players.get(row, "notes"), note))
        for field, value in zip(IMAGE_FIELDS, fix.image or (None,) * len(IMAGE_FIELDS)):
            players.set(row, field, value)
        new_values = (
            f"{fix.new_qid} / {fix.date_of_birth} / {fix.place_of_birth}, {fix.birth_country} / "
            f"{fix.image[0] if fix.image else 'no photo'}"
        )
        slug = re.sub(r"[^a-z]+", "_", fix.squad_name.lower().replace("á", "a")).strip("_")
        changes.append(change_row(
            f"chg_{FIX_DATE}_{slug}_identity", fix.team, fix.player_id, "identity_correction",
            "wikidata_id, date_of_birth, place_of_birth, birth_country, bio_source_url, image_*",
            old_values, new_values, SQUADS_URL,
            f"Wrong-person match: {fix.old_qid} is a namesake ({fix.old_entity}). Wikipedia's final squad "
            f"lists {fix.squad_name} as {fix.squad_description}, which matches {fix.new_qid}.{photo}",
        ))
        print(f"Identity corrected: {fix.squad_name} ({fix.team}) {fix.old_qid} -> {fix.new_qid}")
    return changes


def fix_name(players: Sheet) -> list[list[object]]:
    row = players.find("player_id", NAME_FIX["player_id"])
    if text(players.get(row, "display_name")) == NAME_FIX["new_name"]:
        return []
    if text(players.get(row, "display_name")) != NAME_FIX["old_name"]:
        raise SystemExit(f"{NAME_FIX['player_id']}: unexpected display_name {players.get(row, 'display_name')!r}")
    squad = wikipedia_squad_row(NAME_FIX["team"], NAME_FIX["new_name"])
    if squad["date_of_birth"] != iso_date(players.get(row, "date_of_birth")):
        raise SystemExit(f"{NAME_FIX['player_id']}: birth date disagrees with Wikipedia's final squad")

    players.set(row, "display_name", NAME_FIX["new_name"])
    players.set(row, "name_ascii", NAME_FIX["new_name"])
    note = (
        f"Name corrected on {FIX_DATE} from '{NAME_FIX['old_name']}', as ESPN's squad list printed it. "
        f"Wikipedia's final squad and FIFA list him as {NAME_FIX['new_name']} (number {squad['shirt_number']}, "
        f"born {squad['date_of_birth']}, {squad['club']}), which matches this record. player_id kept."
    )
    players.set(row, "notes", append_note(players.get(row, "notes"), note))
    print(f"Name corrected: {NAME_FIX['old_name']} -> {NAME_FIX['new_name']}")
    return [change_row(
        f"chg_{FIX_DATE}_ali_nemati_name", NAME_FIX["team"], NAME_FIX["player_id"], "correction",
        "display_name, name_ascii", NAME_FIX["old_name"], NAME_FIX["new_name"], SQUADS_URL, note,
    )]


def clean_sources(sources: Sheet, change_log: Sheet) -> list[list[object]]:
    logged = [
        tuple(text(change_log.get(row, field)) for field in ("player_id", "old_value", "new_value"))
        for row in change_log.rows()
    ]
    misplaced = []
    for row in sources.rows():
        source_id = text(sources.get(row, "source_id"))
        if source_id not in MISPLACED_SOURCE_IDS:
            continue
        player_id = text(sources.get(row, "source_type"))
        old_club = text(sources.get(row, "title"))
        new_club = text(sources.get(row, "published_at"))
        if not any(p == player_id and old.startswith(old_club) and new.startswith(new_club) for p, old, new in logged):
            raise SystemExit(f"sources {source_id}: no matching change_log row, so it is not safe to remove")
        misplaced.append((row[0].row, source_id))
    for row_number, _ in sorted(misplaced, reverse=True):
        sources.ws.delete_rows(row_number)

    existing = {text(sources.get(row, "source_id")) for row in sources.rows()}
    added = [entry for entry in NEW_SOURCES if entry[0] not in existing]
    for entry in added:
        sources.ws.append([value or None for value in entry])

    if not misplaced and not added:
        return []
    print(f"Sources: removed {len(misplaced)} misplaced rows, registered {len(added)} sources")
    removed_ids = ", ".join(source_id for _, source_id in sorted(misplaced, key=lambda item: item[1])) or "none"
    added_ids = ", ".join(entry[0] for entry in added) or "none"
    return [change_row(
        f"chg_{FIX_DATE}_sources_registry", "ALL", None, "bulk_update", "sources rows",
        f"removed: {removed_ids}", f"added: {added_ids}", None,
        "The removed rows were club corrections pasted into sources with shifted columns; each one is "
        "already logged as chg_step5_0002 to chg_step5_0006. The added rows register the other sources "
        "the pipeline used: ESPN, Wikidata, Wikimedia Commons, GeoNames, and the pages read by hand.",
    )]


def sync_links(players: Sheet) -> list[list[object]]:
    """Point each URL cell's hyperlink at the URL the cell shows."""
    synced = 0
    for row in players.rows():
        for field in sorted(LINKED_FIELDS):
            cell = row[players.col[field]]
            value = text(cell.value)
            target = cell.hyperlink.target if cell.hyperlink is not None else None
            if value.startswith("http") and target != value:
                cell.hyperlink = value
                synced += 1
    if not synced:
        return []
    print(f"Hyperlinks synced to their cell's URL: {synced}")
    return [change_row(
        f"chg_{FIX_DATE}_bio_source_links", "ALL", None, "correction", "players.bio_source_url hyperlinks",
        "linked to Wikipedia's squads page", "linked to the URL each cell shows", None,
        f"{synced} late replacements showed their Wikidata URL in bio_source_url, but the cell's link opened "
        "Wikipedia's squads page. Exports were not affected: they read the cell text.",
    )]


def set_match_methods(players: Sheet) -> list[list[object]]:
    ws = players.ws
    if MATCH_METHOD in players.col:
        index = players.col[MATCH_METHOD]
    else:
        index = max(players.col.values()) + 1
        header = ws.cell(row=1, column=index + 1, value=MATCH_METHOD)
        header._style = copy(ws.cell(row=1, column=index)._style)
        ws.column_dimensions[get_column_letter(index + 1)].width = 14
        if ws.auto_filter.ref:
            min_col, min_row, max_col, max_row = range_boundaries(ws.auto_filter.ref)
            if max_col == index:
                ws.auto_filter.ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(index + 1)}{max_row}"
        players.headers = [cell.value for cell in ws[1]]
        players.col[MATCH_METHOD] = index

    counts = {"auto": 0, "dob": 0, "manual": 0}
    changed = 0
    for row in players.rows():
        method = match_method(
            text(players.get(row, "data_confidence")),
            text(players.get(row, "notes")),
            text(players.get(row, "wikidata_id")),
        )
        counts[method] += 1
        cell = ws.cell(row=row[0].row, column=index + 1)
        if cell.value != method:
            cell.value = method
            changed += 1
    if not changed:
        return []
    summary = ", ".join(f"{name} {count}" for name, count in counts.items())
    print(f"match_method set on {changed} rows ({summary})")
    return [change_row(
        f"chg_{FIX_DATE}_match_method", "ALL", None, "bulk_update", "players.match_method (new column)",
        None, summary, None,
        "How each identity match was settled. auto: the matcher's high-confidence pick, unchanged since. "
        "dob: a late replacement matched by name and confirmed by birth date. manual: settled by hand, "
        "including auto matches corrected later. data_confidence keeps the matcher's first verdict.",
    )]


def main() -> None:
    wb = load_workbook(WB_PATH)
    players = Sheet(wb["players"])
    sources = Sheet(wb["sources"])
    change_log = Sheet(wb["change_log"])

    changes = []
    changes += fix_identities(players)
    changes += fix_name(players)
    changes += clean_sources(sources, change_log)
    changes += sync_links(players)
    changes += set_match_methods(players)

    if not changes:
        print("Nothing to change: every fix is already in the workbook.")
        return
    logged_ids = {text(change_log.get(row, "change_id")) for row in change_log.rows()}
    new_changes = [change for change in changes if change[0] not in logged_ids]
    for change in new_changes:
        change_log.ws.append(change)

    backup = WB_PATH.with_name(f"{WB_PATH.stem}.backup_{date.today().isoformat()}.xlsx")
    shutil.copy2(WB_PATH, backup)
    print(f"Backup written: {backup.relative_to(REPO_ROOT)}")
    wb.save(WB_PATH)
    verify_saved_workbook()
    print(f"Saved {WB_PATH.relative_to(REPO_ROOT)} with {len(new_changes)} change_log rows")


def verify_saved_workbook() -> None:
    """Read the saved file back and check the corrected rows hold their new values."""
    players = Sheet(load_workbook(WB_PATH)["players"])
    for fix in IDENTITY_FIXES:
        row = players.find("player_id", fix.player_id)
        expected = {
            "wikidata_id": fix.new_qid,
            "date_of_birth": fix.date_of_birth,
            "place_of_birth": fix.place_of_birth,
            "bio_source_url": f"https://www.wikidata.org/wiki/{fix.new_qid}",
            **dict(zip(IMAGE_FIELDS, fix.image or ("",) * len(IMAGE_FIELDS))),
        }
        for field, value in expected.items():
            found = iso_date(players.get(row, field)) if field == "date_of_birth" else text(players.get(row, field))
            if found != value:
                raise SystemExit(f"{fix.player_id}.{field} reads back as {found!r}, not {value!r}")
    row = players.find("player_id", NAME_FIX["player_id"])
    if text(players.get(row, "display_name")) != NAME_FIX["new_name"]:
        raise SystemExit(f"{NAME_FIX['player_id']}.display_name did not save")


if __name__ == "__main__":
    main()
