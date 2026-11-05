"""The change_log notes, which the Methodology page shows as written.

They are read by visitors, so they use plain words: no table or column names,
no em dashes, and scores with an en dash ("1–2"), as on the match pages, so a
score cannot break across lines.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

CHANGE_LOG = Path(__file__).resolve().parents[1] / "data" / "processed" / "app_exports" / "change_log.json"
NOTES = [(row["change_id"], row["notes"] or "") for row in json.loads(CHANGE_LOG.read_text(encoding="utf-8"))]

SCORE_WITH_HYPHEN = re.compile(r"(?<![-\d])\d+-\d+(?![-\d])")  # 1-2, but not a date such as 2026-11-05
FIELD_NAME = re.compile(r"\b[a-z]+_[a-z_]+\b|\b[a-z_]+\.[a-z_]+\b")  # date_of_birth, players.match_method


@pytest.mark.parametrize("change_id, note", NOTES, ids=[change_id for change_id, _ in NOTES])
def test_note_is_plain(change_id: str, note: str) -> None:
    assert note, "every change needs a note"
    assert "—" not in note, "em dash in the note"
    assert not SCORE_WITH_HYPHEN.search(note), "score written with a hyphen; use an en dash"
    assert not FIELD_NAME.search(note), f"field or table name in the note: {FIELD_NAME.search(note).group()}"
