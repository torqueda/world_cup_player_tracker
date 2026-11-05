#!/usr/bin/env python3
"""
Follow-ups to the 2026-11-05 data fixes, applied to the master workbook.

Run after apply_2026_11_data_fixes.py. Writes a backup next to the workbook
first (git ignores it), then:

1. Sets 27 birth dates to FIFA's. These are the players whose birth date
   disagreed with Wikipedia's final squads, which give the dates from FIFA's
   squad lists (data/quality/identity_review.csv before this change). Where
   FIFA and another source disagree, the dataset uses FIFA
   (docs/decision_log.md, 2026-11-05). Each player's notes say what changed,
   and one change_log row lists every date.
2. Rewords the change_log notes in plain words, for the Methodology page,
   which shows them. Scores take an en dash, as on the match pages, so that
   "1–2" cannot break across lines. The other columns keep their values.

Every step checks the workbook's current value before changing it, so a
second run changes nothing.

Usage:
    python scripts/data_pipeline/apply_2026_11_data_fixes.py
    python scripts/data_pipeline/apply_2026_11_birth_dates_and_notes.py
    python scripts/export/refresh_all_exports.py
"""

from __future__ import annotations

import shutil
from datetime import date, datetime

from openpyxl import load_workbook

from reconcile_final_rosters import TEAM_ALIASES
from apply_2026_11_data_fixes import (
    FIX_DATE,
    REPO_ROOT,
    SQUADS_URL,
    WB_PATH,
    Sheet,
    append_note,
    change_row,
    iso_date,
    text,
    wikipedia_squad_row,
)

# player_id, team, name in Wikipedia's final squad, our old date, FIFA's date
FIFA_BIRTH_DATES = (
    ("p_can_nathan_saliba_7a28cc90", "Canada", "Nathan Saliba", "2004-08-29", "2004-02-07"),
    ("p_cod_edo_kayembe_5143c1cb", "Congo DR", "Edo Kayembe", "1998-08-03", "1998-06-03"),
    ("p_col_willer_ditta_aa30458a", "Colombia", "Willer Ditta", "1997-01-23", "1998-01-23"),
    ("p_col_cucho_hernandez_b18b9740", "Colombia", "Cucho Hernández", "1999-04-22", "1999-04-20"),
    ("p_egy_mohamed_hany_f4c4265d", "Egypt", "Mohamed Hany", "1996-01-25", "1996-02-02"),
    ("p_egy_el_mahdy_soliman_378a11ec", "Egypt", "El Mahdy Soliman", "1986-11-30", "1987-06-08"),
    ("p_gha_brandon_thomas_asante_a966ba92", "Ghana", "Brandon Thomas-Asante", "1999-12-29", "1998-12-29"),
    ("p_gha_benjamin_asare_6451594e", "Ghana", "Benjamin Asare", "1992-01-01", "1992-07-13"),
    ("p_hai_martin_experience_fa6fe29c", "Haiti", "Martin Expérience", "1998-03-09", "1999-03-09"),
    ("p_irn_alireza_beiranvand_c79fbeca", "Iran", "Alireza Beiranvand", "1992-09-22", "1992-09-21"),
    ("p_irn_saleh_hardani_78f246fd", "Iran", "Saleh Hardani", "1996-09-14", "1998-12-26"),
    ("p_irq_manaf_younis_460d1a76", "Iraq", "Manaf Younis", "1996-12-29", "1996-11-16"),
    ("p_jor_odeh_al_fakhouri_753f9683", "Jordan", "Odeh Al-Fakhouri", "2005-11-20", "2005-11-22"),
    ("p_jor_abdallah_al_fakhouri_696806b1", "Jordan", "Abdallah Al-Fakhouri", "2000-02-22", "2000-01-22"),
    ("p_ksa_ali_majrashi_f27c8815", "Saudi Arabia", "Ali Majrashi", "1999-10-01", "1999-10-02"),
    ("p_ksa_ali_lajami_81d185fd", "Saudi Arabia", "Ali Lajami", "1996-04-25", "1996-04-24"),
    ("p_ksa_khalid_al_ghannam_b44eecee", "Saudi Arabia", "Khalid Al-Ghannam", "2000-11-07", "2000-11-08"),
    ("p_ksa_abdullah_al_hamdan_e6c2e57f", "Saudi Arabia", "Abdullah Al-Hamdan", "1999-09-12", "1999-09-13"),
    ("p_ksa_moteb_al_harbi_e138f807", "Saudi Arabia", "Moteb Al-Harbi", "2000-02-19", "2000-02-20"),
    ("p_pan_jose_cordoba_5e989cc4", "Panama", "José Córdoba", "2001-03-06", "2001-06-03"),
    ("p_pan_cesar_samudio_51e540e4", "Panama", "César Samudio", "1994-03-26", "1994-02-23"),
    ("p_par_andres_cubas_23543da5", "Paraguay", "Andrés Cubas", "1996-06-22", "1996-05-11"),
    ("p_par_gabriel_avalos_3d7a0590", "Paraguay", "Gabriel Ávalos", "1990-10-12", "1991-07-09"),
    ("p_qat_abdulaziz_hatem_1df7c78b", "Qatar", "Abdulaziz Hatem", "1990-10-28", "1990-01-01"),
    ("p_rsa_nkosinathi_sibisi_c2a232db", "South Africa", "Nkosinathi Sibisi", "1995-05-22", "1995-09-22"),
    ("p_sen_el_hadji_malick_diouf_2fb2dad9", "Senegal", "El Hadji Malick Diouf", "2004-12-28", "2004-12-29"),
    ("p_swe_erik_smith_9cafee29", "Sweden", "Eric Smith", "1997-01-05", "1997-01-08"),
)
BIRTH_DATES_CHANGE_ID = f"chg_{FIX_DATE}_fifa_birth_dates"
NOTES_CHANGE_ID = f"chg_{FIX_DATE}_plain_notes"

# change_id: (how the current note starts, the note in plain words).
# The start is checked before a note is replaced, so a note edited by hand
# since is left alone and reported.
PLAIN_NOTES = {
    "chg_step5_0001": (
        "Corrected ESPN/source spelling issue",
        "ESPN's squad list spelled his name Ali Yousef. He is Ali Yousif, and his player ID now uses that spelling.",
    ),
    "chg_step5_0002": (
        "ESPN listed Heart of Midlothian/Hearts",
        "ESPN listed his club as Hearts. An official club announcement shows he was called up from "
        "Rangers F.C., so the dataset uses Rangers.",
    ),
    "chg_step5_0003": (
        "ESPN listed Al-Khor",
        "ESPN listed his club as Al-Khor. His player profile shows he was called up from Al-Karma SC, "
        "so the dataset uses Al-Karma.",
    ),
    "chg_step5_0004": (
        "ESPN listed Al-Shorta",
        "ESPN listed his club as Al-Shorta. His player profile shows he was called up from Dibba FC, "
        "so the dataset uses Dibba.",
    ),
    "chg_step5_0005": (
        "ESPN listed Hamburg SV",
        "ESPN listed his club as Hamburg SV, a misspelling of Hamburger SV.",
    ),
    "chg_step5_0006": (
        "ESPN listed Hamburg",
        "ESPN listed his club as Hamburg. His player profile shows the club is Hamburger SV.",
    ),
    "chg_2026-07-12_final_dataset_import": (
        "Imported final-dataset collection of 2026-07-12",
        "Added the final squads, tournament stats, matches, coaches and referees collected on 12 July. "
        "Twelve clubs that had been entered as placeholders were merged into their real records, caps and "
        "goals were filled in for the 27 late replacements, and FIFA's spelling of Mohammad Taha's name "
        "was recorded.",
    ),
    "chg_2026-07-12_enrichment": (
        "Wikidata DOB-confirmed birthplace enrichment",
        "Added birthplaces from Wikidata for the 27 late replacements, each confirmed by birth date, and "
        "goalkeeping stats for 60 goalkeepers.",
    ),
    "chg_2026-07-13_gaziantep_league": (
        "Gaziantep F.K. league value was the stray",
        "Gaziantep F.K.'s league read \"dissolution\", a note that had landed in the wrong column. "
        "It is now Süper Lig.",
    ),
    "chg_2026-08-19_post_final_refresh": (
        "Post-tournament refresh",
        "Updated the data after the final: squads and match officials from Wikipedia, and player stats, "
        "team stats and results from FIFA. Semi-finals: France 0–2 Spain and England 1–2 Argentina. "
        "Third place: France 4–6 England. Final: Spain 1–0 Argentina after extra time. No squad had "
        "changed since the semi-finals. Goalkeeping stats were updated separately the same day.",
    ),
    "chg_2026-08-19_gk_stats_refresh": (
        "Refreshed goalkeeping stats",
        "Updated the goalkeeping stats (saves, and actions inside and outside the box) to final "
        "tournament totals for all 61 goalkeepers.",
    ),
    "chg_2026-11-05_ali_nemati_name": (
        "Name corrected on 2026-11-05",
        "ESPN's squad list printed this name as \"Ali Nemati Omid Noorafkan\", joining two Iran players. "
        "FIFA and Wikipedia list number 19 (born 8 February 1996, Foolad) as Ali Nemati, which matches "
        "this record. Omid Noorafkan is a separate player.",
    ),
    "chg_2026-11-05_sources_registry": (
        "The removed rows were club corrections",
        "Removed five rows that were club corrections pasted into the sources list by mistake; each one "
        "is already in this log as a club change. Added the other sources the data came from: ESPN, "
        "Wikidata, Wikimedia Commons, GeoNames, and the pages read by hand.",
    ),
    "chg_2026-11-05_bio_source_links": (
        "27 late replacements showed their Wikidata URL",
        "For the 27 late replacements, the workbook's source link opened Wikipedia's squads page instead "
        "of the Wikidata page it showed. The site was not affected.",
    ),
    "chg_2026-11-05_match_method": (
        "How each identity match was settled",
        "Recorded how each player's match to Wikidata was settled: automatically by the matcher, by name "
        "and birth date (the late replacements), or by hand, including automatic matches corrected later.",
    ),
}


def long_date(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.day} {day:%B %Y}"


# The identity fixes: their notes are built from the same facts as the change row.
# change_id: (player, wrongly matched entity, its description, right entity,
# squad description, what the player record took from the right entity)
IDENTITY_NOTES = {
    "chg_2026-11-05_alisson_identity": (
        "Alisson", "Q4727251", f"a midfielder born {long_date('1993-06-25')}", "Q18237361",
        f"a Liverpool goalkeeper born {long_date('1992-10-02')}", "its birth date, birthplace and photo"),
    "chg_2026-11-05_liam_kelly_identity": (
        "Liam Kelly", "Q772315", f"a midfielder born {long_date('1990-02-10')}", "Q27448075",
        f"a Rangers goalkeeper born {long_date('1996-01-23')}",
        "its birth date and birthplace. That record has no photo, so the other Liam Kelly's photo was removed"),
    "chg_2026-11-05_ross_stewart_identity": (
        "Ross Stewart", "Q16237030", f"a goalkeeper born {long_date('1995-04-16')}", "Q47126518",
        f"a Southampton forward born {long_date('1996-07-11')}", "its birth date and birthplace"),
    "chg_2026-11-05_jorge_sanchez_identity": (
        "Jorge Sánchez", "Q11073995", f"a midfielder born {long_date('1993-02-14')}", "Q24034870",
        f"a PAOK defender born {long_date('1997-12-10')}", "its birth date and birthplace"),
    "chg_2026-11-05_kim_tae_hyeon_identity": (
        "Kim Tae-hyeon", "Q61100326", f"a midfielder born {long_date('1996-12-19')}", "Q79904514",
        f"a Kashima Antlers defender born {long_date('2000-09-17')}",
        "its birth date and birthplace, and his name now follows FIFA's spelling"),
}
for change_id, (name, old_qid, old_entity, new_qid, squad, taken) in IDENTITY_NOTES.items():
    PLAIN_NOTES[change_id] = (
        "Wrong-person match",
        f"{name} was linked to the wrong Wikidata record ({old_qid}), a namesake: {old_entity}. "
        f"The World Cup squad lists give {squad}, so the player now links to that record ({new_qid}), "
        f"with {taken}.",
    )


def set_fifa_birth_dates(players: Sheet) -> list[list[object]]:
    changed = []
    for player_id, team, squad_name, old, fifa in FIFA_BIRTH_DATES:
        squad = wikipedia_squad_row(TEAM_ALIASES.get(team, team), squad_name)
        if squad["date_of_birth"] != fifa:
            raise SystemExit(f"{player_id}: Wikipedia's final squad gives {squad['date_of_birth']}, not {fifa}")
        row = players.find("player_id", player_id)
        current = iso_date(players.get(row, "date_of_birth"))
        if current == fifa:
            continue
        if current != old:
            raise SystemExit(f"{player_id}: expected date_of_birth {old}, found {current!r}; not changing it")
        players.set(row, "date_of_birth", datetime.fromisoformat(fifa))
        players.set(row, "notes", append_note(
            players.get(row, "notes"),
            f"Birth date set on {FIX_DATE} from {old} to {fifa}, the date in FIFA's squad list "
            "(as Wikipedia's final squads give it).",
        ))
        changed.append((player_id, old, fifa))
    if not changed:
        return []
    print(f"Birth dates set to FIFA's: {len(changed)}")
    return [change_row(
        BIRTH_DATES_CHANGE_ID, "ALL", None, "correction", "players.date_of_birth",
        "; ".join(f"{player_id} {old}" for player_id, old, _ in changed),
        "; ".join(f"{player_id} {fifa}" for player_id, _, fifa in changed),
        SQUADS_URL,
        f"Set {len(changed)} birth dates to the ones in FIFA's squad lists, where our source gave another "
        "date. Most were a day or two apart, exactly a year apart, or had the day and month swapped. "
        "Where FIFA and another source disagree, the dataset uses FIFA.",
    )]


def plain_notes(change_log: Sheet) -> int:
    reworded = 0
    for change_id, (start, note) in PLAIN_NOTES.items():
        row = change_log.find("change_id", change_id)
        current = text(change_log.get(row, "notes"))
        if current == note:
            continue
        if not current.startswith(start):
            raise SystemExit(f"change_log {change_id}: the note starts {current[:40]!r}, not {start!r}; not changing it")
        change_log.set(row, "notes", note)
        reworded += 1
    return reworded


def main() -> None:
    wb = load_workbook(WB_PATH)
    players = Sheet(wb["players"])
    change_log = Sheet(wb["change_log"])

    changes = set_fifa_birth_dates(players)
    logged = {text(change_log.get(row, "change_id")) for row in change_log.rows()}
    for change in changes:
        if change[0] not in logged:
            change_log.ws.append(change)
    reworded = plain_notes(change_log)
    if reworded:
        print(f"change_log notes reworded: {reworded}")
        if NOTES_CHANGE_ID not in logged:
            change_log.ws.append(change_row(
                NOTES_CHANGE_ID, "ALL", None, "correction", "change_log.notes", None, None, None,
                "Reworded the notes in this log in plain words, and wrote scores with an en dash. "
                "What each entry records is unchanged.",
            ))
    if not changes and not reworded:
        print("Nothing to change: every follow-up is already in the workbook.")
        return

    backup = WB_PATH.with_name(f"{WB_PATH.stem}.backup_{date.today().isoformat()}_follow_ups.xlsx")
    shutil.copy2(WB_PATH, backup)
    print(f"Backup written: {backup.relative_to(REPO_ROOT)}")
    wb.save(WB_PATH)
    verify_saved_workbook()
    print(f"Saved {WB_PATH.relative_to(REPO_ROOT)}")


def verify_saved_workbook() -> None:
    """Read the saved file back and check every changed value."""
    wb = load_workbook(WB_PATH)
    players = Sheet(wb["players"])
    for player_id, _, _, _, fifa in FIFA_BIRTH_DATES:
        found = iso_date(players.get(players.find("player_id", player_id), "date_of_birth"))
        if found != fifa:
            raise SystemExit(f"{player_id}.date_of_birth reads back as {found!r}, not {fifa!r}")
    change_log = Sheet(wb["change_log"])
    for change_id, (_, note) in PLAIN_NOTES.items():
        if text(change_log.get(change_log.find("change_id", change_id), "notes")) != note:
            raise SystemExit(f"change_log {change_id}: the reworded note did not save")


if __name__ == "__main__":
    main()
