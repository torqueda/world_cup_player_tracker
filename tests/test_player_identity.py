"""Identity checks against a second source, and the linking rule they rely on.

The integrity checks in test_export_invariants.py cannot tell a complete record
of the wrong person from the right one. These compare each active player with
Wikipedia's final squad (birth date) and with the matched Wikidata entity's
position, through scripts/validation/check_player_identity.py.

Every finding has to be listed in data/quality/identity_review.csv with its
current values. When one of these tests fails, run
    python scripts/validation/check_player_identity.py --write
then look at the new rows and set their status and note.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_script(relative_path: str):
    path = REPO / relative_path
    if path.stem in sys.modules:  # already imported by another script
        return sys.modules[path.stem]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


identity = load_script("scripts/validation/check_player_identity.py")
reconcile = load_script("scripts/data_pipeline/reconcile_final_rosters.py")


@pytest.fixture(scope="module")
def findings():
    return identity.find_all()


@pytest.fixture(scope="module")
def reviewed():
    return identity.read_review_file()


def test_every_identity_finding_is_in_the_review_file(findings, reviewed) -> None:
    unlisted = [f"{f.check} {f.display_name} ({f.team}): {f.ours} vs {f.second_source}" for f in findings if f.key not in reviewed]
    assert not unlisted, f"new identity findings, add them to identity_review.csv: {unlisted}"


def test_review_file_lists_only_current_findings(findings, reviewed) -> None:
    current = {f.key for f in findings}
    stale = [f"{key[0]} {row['display_name']} ({row['team']})" for key, row in reviewed.items() if key not in current]
    assert not stale, f"identity_review.csv rows that no longer disagree, remove them: {stale}"


def test_review_statuses_are_known(reviewed) -> None:
    unknown = {row["status"] for row in reviewed.values()} - set(identity.STATUSES)
    assert not unknown, f"unknown status values in identity_review.csv: {sorted(unknown)}"


def test_every_active_player_is_linked_to_the_final_squad() -> None:
    squad_entries = json.loads((REPO / "data/processed/app_exports/squad_entries.json").read_text(encoding="utf-8"))
    active = {e["player_id"] for e in squad_entries if e["squad_status"] == "active"}
    linked = {ours["player_id"] for ours, _ in identity.linked_players()}
    assert active - linked == set(), f"active players with no row in Wikipedia's final squad: {sorted(active - linked)[:5]}"


def test_every_player_says_how_the_match_was_settled() -> None:
    players = json.loads((REPO / "data/processed/app_exports/players.json").read_text(encoding="utf-8"))
    wrong = [p["player_id"] for p in players if p.get("match_method") not in ("auto", "dob", "manual")]
    assert not wrong, f"players without a valid match_method: {wrong[:5]}"


# The linking rule ------------------------------------------------------------


def ours(name: str, dob: str) -> dict[str, str]:
    return {"folded": reconcile.fold(name), "date_of_birth": dob}


def theirs(name: str, dob: str) -> dict[str, str]:
    return {"player_name": name, "date_of_birth": dob}


def methods(links: list[tuple[int, int, str]]) -> list[str]:
    return [method.split(":")[0] for _, _, method in links]


def test_identical_names_link_exactly() -> None:
    links = reconcile.link_team([ours("Aïssa Mandi", "1991-10-22")], [theirs("Aissa Mandi", "1991-10-22")])
    assert links == [(0, 0, "exact")]


def test_close_names_link_without_a_shared_birthday() -> None:
    links = reconcile.link_team([ours("Achraf Abada", "1999-01-01")], [theirs("Achref Abada", "2000-01-01")])
    assert methods(links) == ["fuzzy"]


def test_a_shared_birthday_links_a_nickname_that_shares_a_word() -> None:
    links = reconcile.link_team([ours("Cameron Devlin", "1998-06-07")], [theirs("Cammy Devlin", "1998-06-07")])
    assert methods(links) == ["fuzzy+dob"]


def test_a_shared_birthday_alone_does_not_link_two_teammates() -> None:
    links = reconcile.link_team([ours("Ricardo Pepi", "2003-01-09")], [theirs("Tyler Adams", "2003-01-09")])
    assert links == []


def test_particles_do_not_count_as_a_shared_word() -> None:
    assert not reconcile.has_name_evidence(reconcile.fold("Ali Al Bulaihi"), reconcile.fold("Salem Al Dawsari"), 0.4)
    assert reconcile.has_name_evidence(reconcile.fold("Yaya Sithole"), reconcile.fold("Sphephelo Sithole"), 0.4)
