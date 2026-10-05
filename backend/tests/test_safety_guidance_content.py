import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.services.safety_guidance import CONTENT_PATH, load_entries


def _entry(**overrides) -> dict:
    entry = {
        "id": "example-entry",
        "question": "An example question?",
        "answer": "A short answer.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
        "reviewed_by": None,
        "applies_when": {},
    }
    entry.update(overrides)
    return entry


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "entries.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_shipped_content_file_loads_in_display_order() -> None:
    entries = load_entries(CONTENT_PATH)

    assert [entry.id for entry in entries] == [
        "when-to-leave",
        "leaving-late-danger",
        "too-late-to-leave",
        "stay-and-defend",
        "emergency-kit",
        "children-comfort",
        "pets-plan",
        "pet-kit",
        "pets-relief-centres",
        "extra-help-leave-early",
        "extra-support-plan",
        "property-prep",
        "extreme-day-home",
    ]


def test_every_shipped_entry_names_a_cfa_page_and_a_real_date() -> None:
    for entry in load_entries(CONTENT_PATH):
        assert urlparse(entry.source_url).hostname == "www.cfa.vic.gov.au"
        # The reviewer re-records this from the live page, so pin only that it is real.
        assert entry.retrieved_on <= date.today()


def test_a_valid_entry_loads(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(applies_when={"has_pets": True})]))

    assert entries[0].applies_when.required() == frozenset({"has_pets"})


def test_an_empty_condition_object_applies_to_everyone(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry()]))

    assert entries[0].applies_when.required() == frozenset()


def test_an_unknown_condition_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(applies_when={"has_children": True})]))


def test_a_condition_set_to_false_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(applies_when={"has_pets": False})]))


def test_a_missing_question_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["question"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_a_missing_source_url_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["source_url"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_a_source_url_that_is_not_https_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(source_url="http://example.com")]))


def test_a_missing_retrieved_on_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["retrieved_on"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        load_entries(_write(tmp_path, [_entry(), _entry(question="Another?")]))


def test_an_id_that_is_not_a_slug_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(id="Not A Slug")]))


def test_an_answer_of_exactly_600_characters_is_accepted(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(answer="a" * 600)]))

    assert len(entries[0].answer) == 600


def test_an_answer_longer_than_600_characters_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(answer="a" * 601)]))


def test_a_reviewer_name_of_only_spaces_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(reviewed_by="   ")]))


def test_a_reviewer_name_is_trimmed(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(reviewed_by="  Ada  ")]))

    assert entries[0].reviewed_by == "Ada"
