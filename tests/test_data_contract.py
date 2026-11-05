"""Every JSON export against the data contract in data/contract/exports.yaml.

The site trusts the exports' shape. These tests fail when a column is renamed,
dropped or added, a required value goes missing, a value falls outside its
allowed set, or a reference points at nothing, so the build stops instead of a
page going blank. They also fail when the generated site types or data
dictionary are out of date with the contract.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / "data" / "processed" / "app_exports"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "export"))

import generate_from_contract as generator  # noqa: E402

CONTRACT = generator.load_contract()
FORMATS = {
    "date": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
    "datetime": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T00:00:00"),
    "url": re.compile(r"https?://\S+"),
}
FIELD_KEYS = {"type", "nullable", "values", "format", "pattern", "references", "description"}
TABLE_KEYS = {"file", "type_name", "key", "read_by", "description", "fields"}
PYTHON_TYPES = {"string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,), "list": (list,)}
NOT_IN_CONTRACT = {"meta.json"}  # a single object of counts, checked by test_export_invariants.py

_cache: dict[str, list[dict]] = {}


def rows(table: str) -> list[dict]:
    if table not in _cache:
        _cache[table] = json.loads((EXPORT_DIR / CONTRACT[table]["file"]).read_text(encoding="utf-8"))
    return _cache[table]


def type_ok(value: object, type_name: str) -> bool:
    if type_name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, PYTHON_TYPES[type_name])


def test_every_export_has_an_entry() -> None:
    exported = {path.name for path in EXPORT_DIR.glob("*.json")} - NOT_IN_CONTRACT
    described = {table["file"] for table in CONTRACT.values()}
    assert exported - described == set(), "exports with no contract entry"
    assert described - exported == set(), "contract entries with no export"


@pytest.mark.parametrize("table", CONTRACT)
def test_entry_is_well_formed(table: str) -> None:
    entry = CONTRACT[table]
    assert set(entry) == TABLE_KEYS, f"{table}: table keys {sorted(set(entry) ^ TABLE_KEYS)}"
    assert entry["key"] in entry["fields"], f"{table}: key {entry['key']} is not a field"
    for path in entry["read_by"]:
        assert (REPO_ROOT / path).is_file(), f"{table}: read_by {path} does not exist"
        assert entry["file"] in (REPO_ROOT / path).read_text(encoding="utf-8"), f"{path} does not import {entry['file']}"
    for name, field in entry["fields"].items():
        assert set(field) <= FIELD_KEYS, f"{table}.{name}: unknown keys {sorted(set(field) - FIELD_KEYS)}"
        assert field["type"] in PYTHON_TYPES, f"{table}.{name}: unknown type {field['type']}"
        assert field.get("description"), f"{table}.{name}: no description"
        assert field.get("format", "date") in FORMATS, f"{table}.{name}: unknown format {field['format']}"
        if "references" in field:
            ref_table, ref_field = field["references"].split(".")
            assert ref_field in CONTRACT[ref_table]["fields"], f"{table}.{name}: bad reference {field['references']}"


@pytest.mark.parametrize("table", CONTRACT)
def test_key_is_unique_and_present(table: str) -> None:
    key = CONTRACT[table]["key"]
    values = [row.get(key) for row in rows(table)]
    assert all(value not in (None, "") for value in values), f"{table}: empty {key}"
    duplicates = sorted({value for value in values if values.count(value) > 1})
    assert not duplicates, f"{table}: duplicate {key}: {duplicates[:5]}"


@pytest.mark.parametrize("table", CONTRACT)
def test_rows_have_exactly_the_contract_fields(table: str) -> None:
    expected = list(CONTRACT[table]["fields"])
    for row in rows(table):
        assert list(row) == expected, (
            f"{table} row {row.get(CONTRACT[table]['key'])}: "
            f"missing {sorted(set(expected) - set(row))}, not in the contract {sorted(set(row) - set(expected))}"
        )


@pytest.mark.parametrize("table", CONTRACT)
def test_values_match_the_contract(table: str) -> None:
    entry = CONTRACT[table]
    problems = []
    for row in rows(table):
        row_id = row.get(entry["key"])
        for name, field in entry["fields"].items():
            value = row.get(name)
            if value is None:
                if not field.get("nullable"):
                    problems.append(f"{row_id}.{name} is null")
                continue
            if not type_ok(value, field["type"]):
                problems.append(f"{row_id}.{name} is {type(value).__name__}, not {field['type']}")
                continue
            items = value if field["type"] == "list" else [value]
            for item in items:
                if field["type"] == "list" and not isinstance(item, str):
                    problems.append(f"{row_id}.{name} has a non-string item {item!r}")
                elif "values" in field and item not in field["values"]:
                    problems.append(f"{row_id}.{name} = {item!r} is not an allowed value")
                elif "format" in field and not FORMATS[field["format"]].fullmatch(item):
                    problems.append(f"{row_id}.{name} = {item!r} is not a {field['format']}")
                elif "pattern" in field and not re.fullmatch(field["pattern"], item):
                    problems.append(f"{row_id}.{name} = {item!r} does not match {field['pattern']}")
    assert not problems, f"{table}: {len(problems)} problems, first: {problems[:5]}"


@pytest.mark.parametrize(
    "table, field",
    [(table, name) for table, entry in CONTRACT.items() for name, field in entry["fields"].items() if "references" in field],
)
def test_references_exist(table: str, field: str) -> None:
    ref_table, ref_field = CONTRACT[table]["fields"][field]["references"].split(".")
    known = {row[ref_field] for row in rows(ref_table)}
    missing = set()
    for row in rows(table):
        value = row[field]
        for item in value if isinstance(value, list) else [value]:
            if item is not None and item not in known:
                missing.add(item)
    assert not missing, f"{table}.{field}: {len(missing)} values not in {ref_table}.{ref_field}, such as {sorted(missing)[:5]}"


@pytest.mark.parametrize("path", [generator.TYPES_TS, generator.DICTIONARY], ids=lambda path: path.name)
def test_generated_file_is_current(path: Path) -> None:
    expected = generator.outputs(CONTRACT)[path]
    assert path.read_text(encoding="utf-8") == expected, (
        f"{path.relative_to(REPO_ROOT)} is out of date: run python scripts/export/generate_from_contract.py"
    )
